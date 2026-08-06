"""
对话理解增强服务 — 意图保持 / 共指消解 / 话题切换检测

功能:
- 意图保持检测 (用户意图是否被模型正确维持)
- 共指消解 (代词/省略指代 → 实体映射)
- 话题切换检测 (话题漂移/硬切换/软切换)
- 对话上下文质量评估
- 基于规则 + 滑动窗口的轻量级实现 (可接入外部 NLP 模型)

设计:
  本服务提供两种模式:
  1. 规则模式 (默认): 基于关键词/模式匹配的轻量级实现, 零外部依赖
 2. 模型模式 (可选): 通过 set_nlp_fn 注入外部 NLP 推理函数
"""

import logging
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

class IntentType(str, Enum):
    """意图类型"""
    QUESTION = "question"          # 提问
    COMMAND = "command"            # 指令
    INFORM = "inform"              # 陈述/告知
    CLARIFICATION = "clarification"  # 澄清
    CONFIRMATION = "confirmation"  # 确认
    COMPLAINT = "complaint"        # 投诉
    GREETING = "greeting"          # 问候
    FAREWELL = "farewell"          # 告别
    UNKNOWN = "unknown"


class TopicSwitchType(str, Enum):
    """话题切换类型"""
    CONTINUATION = "continuation"  # 同一话题继续
    SOFT_SWITCH = "soft_switch"    # 软切换 (相关话题)
    HARD_SWITCH = "hard_switch"    # 硬切换 (无关话题)
    RETURN = "return"              # 回到之前的话题
    UNKNOWN = "unknown"


class CoreferenceType(str, Enum):
    """共指类型"""
    PRONOUN = "pronoun"            # 代词: 他/她/它/this/that
    DEMONSTRATIVE = "demonstrative"  # 指示词: 这个/那个
    ELLIPSIS = "ellipsis"          # 省略: 补全省略的主语/宾语
    IMPLICIT = "implicit"          # 隐式指代


@dataclass
class IntentResult:
    """意图识别结果"""
    text: str = ""
    intent: str = "unknown"
    confidence: float = 0.0
    entities: list[dict] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass
class CoreferenceResult:
    """共指消解结果"""
    original_text: str = ""
    resolved_text: str = ""
    mentions: list[dict] = field(default_factory=list)  # [{span, type, antecedent, confidence}]
    resolution_count: int = 0


@dataclass
class TopicSwitchResult:
    """话题切换检测结果"""
    switch_type: str = "continuation"
    previous_topic: str = ""
    current_topic: str = ""
    confidence: float = 0.0
    topic_keywords: list[str] = field(default_factory=list)
    distance_score: float = 0.0  # 0=same topic, 1=completely different


@dataclass
class DialogueTurn:
    """对话轮次"""
    role: str = ""
    content: str = ""
    timestamp: float = 0
    intent: Optional[IntentResult] = None
    topic: str = ""


@dataclass
class ContextQuality:
    """上下文质量评估"""
    overall_score: float = 0.0      # 0-100
    intent_consistency: float = 0.0  # 意图一致性
    topic_coherence: float = 0.0     # 话题连贯性
    coreference_resolution: float = 0.0  # 共指消解覆盖率
    context_completeness: float = 0.0  # 上下文完整度
    issues: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


# ============================================================
# 规则引擎 (轻量级 NLP)
# ============================================================

class RuleBasedNLP:
    """基于规则的轻量级 NLP 引擎"""

    # 意图关键词模式
    INTENT_PATTERNS = {
        IntentType.QUESTION: [
            r"[？\?]$", r"^什么", r"^怎么", r"^如何", r"^为什么", r"^哪个", r"^多少",
            r"^请问", r"^能否", r"^可以.*吗", r"^是不是", r"^有没有",
            r"^what\b", r"^how\b", r"^why\b", r"^which\b", r"^where\b", r"^when\b",
            r"^can\b", r"^is\b.*\?", r"^do\b.*\?", r"^does\b.*\?",
        ],
        IntentType.COMMAND: [
            r"^请", r"^帮我", r"^执行", r"^运行", r"^创建", r"^删除", r"^修改",
            r"^设置", r"^打开", r"^关闭", r"^发送", r"^搜索",
            r"^please\b", r"^run\b", r"^create\b", r"^delete\b", r"^send\b",
        ],
        IntentType.INFORM: [
            r"^我", r"^觉得", r"^认为", r"^知道", r"^发现", r"^注意",
            r"^I think", r"^I know", r"^I found", r"^I noticed",
        ],
        IntentType.CLARIFICATION: [
            r"就是说", r"你的意思是", r"换句话说", r"也就是说",
            r"you mean", r"in other words", r"so basically",
        ],
        IntentType.CONFIRMATION: [
            r"好的", r"对的", r"是的", r"没错", r"确认",
            r"\byes\b", r"\bok\b", r"\bcorrect\b", r"\bright\b",
        ],
        IntentType.COMPLAINT: [
            r"不好", r"太慢", r"有问题", r"错误", r"失败", r"不行",
            r"bad\b", r"slow\b", r"error\b", r"fail\b", r"broken\b",
        ],
        IntentType.GREETING: [
            r"^你好", r"^嗨", r"^哈喽", r"^早上好", r"^下午好",
            r"^hello\b", r"^hi\b", r"^hey\b", r"^good morning\b",
        ],
        IntentType.FAREWELL: [
            r"^再见", r"^拜拜", r"^下次见", r"^告辞",
            r"^bye\b", r"^goodbye\b", r"^see you\b",
        ],
    }

    # 代词映射
    PRONOUN_MAP = {
        "他": "PERSON", "她": "PERSON", "它": "THING",
        "这个": "THING", "那个": "THING", "这些": "THINGS", "那些": "THINGS",
        "这里": "PLACE", "那里": "PLACE",
        "his": "PERSON", "her": "PERSON", "its": "THING",
        "this": "THING", "that": "THING",
        "they": "PERSONS", "them": "PERSONS",
        "it": "THING", "he": "PERSON", "she": "PERSON",
    }

    # 话题关键词提取 (简单 TF 模型)
    STOP_WORDS = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "it", "this", "that", "as",
        "i", "you", "he", "she", "we", "they", "me", "him", "her", "us", "them",
        "my", "your", "his", "our", "their", "its",
        "and", "or", "but", "not", "so", "if", "then", "than", "too", "very",
    }

    # 话题分类关键词库
    TOPIC_KEYWORDS = {
        "programming": ["代码", "编程", "python", "java", "javascript", "函数", "变量", "类", "接口",
                        "code", "program", "function", "class", "api", "debug", "bug", "compile"],
        "database": ["数据库", "sql", "查询", "表", "索引", "事务", "连接池",
                     "database", "query", "table", "index", "transaction", "redis", "mysql", "postgres"],
        "deployment": ["部署", "上线", "运维", "docker", "kubernetes", "k8s", "ci/cd", "nginx",
                       "deploy", "container", "pod", "service", "ingress"],
        "ai_ml": ["模型", "训练", "推理", "embedding", "向量", "llm", "gpt", "claude", "prompt",
                  "model", "train", "inference", "neural", "machine learning", "deep learning"],
        "security": ["安全", "认证", "授权", "加密", "token", "jwt", "ssl", "tls",
                     "security", "auth", "encrypt", "permission", "vulnerability"],
        "frontend": ["前端", "页面", "组件", "css", "html", "react", "vue", "ui", "ux",
                     "frontend", "component", "style", "layout", "design"],
        "backend": ["后端", "接口", "服务", "微服务", "rest", "grpc", "消息队列",
                    "backend", "server", "microservice", "restful", "queue"],
        "testing": ["测试", "单元测试", "集成测试", "自动化测试", "pytest", "junit",
                    "test", "unittest", "integration", "mock", "assert"],
    }

    def detect_intent(self, text: str) -> IntentResult:
        """检测用户意图"""
        text_stripped = text.strip()
        text_lower = text_stripped.lower()
        best_intent = IntentType.UNKNOWN
        best_confidence = 0.0

        for intent, patterns in self.INTENT_PATTERNS.items():
            matches = sum(1 for p in patterns if re.search(p, text_lower))
            if matches > 0:
                confidence = min(1.0, 0.5 + matches * 0.2)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_intent = intent

        # 提取关键词
        keywords = self._extract_keywords(text_stripped)

        # 提取实体 (简单正则)
        entities = self._extract_entities(text_stripped)

        return IntentResult(
            text=text_stripped,
            intent=best_intent.value,
            confidence=round(best_confidence, 3),
            entities=entities,
            keywords=keywords,
        )

    def resolve_coreference(self, text: str, context: list[dict]) -> CoreferenceResult:
        """共指消解 (基于规则)"""
        if not context:
            return CoreferenceResult(original_text=text, resolved_text=text, resolution_count=0)

        result = CoreferenceResult(original_text=text, mentions=[])
        resolved = text

        # 构建先行词索引 (最近的名词短语)
        antecedents = []
        for msg in reversed(context[-10:]):  # 最近 10 条
            content = msg.get("content", "")
            # 简单实体提取
            ents = self._extract_entities(content)
            for e in ents:
                antecedents.append(e)
            # 提取名词短语 (简化: 中文 2-6 字词组)
            noun_phrases = re.findall(r'[\u4e00-\u9fff]{2,6}', content)
            for np in noun_phrases:
                if np not in [a["text"] for a in antecedents]:
                    antecedents.append({"text": np, "type": "NP"})

        if not antecedents:
            return CoreferenceResult(original_text=text, resolved_text=text, resolution_count=0)

        # 代词替换
        for pronoun, ent_type in self.PRONOUN_MAP.items():
            if pronoun in resolved and antecedents:
                # 找到匹配类型的先行词
                matching = [a for a in antecedents if a.get("type", "").startswith(ent_type[:4])]
                if matching:
                    antecedent = matching[0]["text"]
                    mention = {
                        "span": pronoun,
                        "type": CoreferenceType.PRONOUN.value,
                        "antecedent": antecedent,
                        "confidence": 0.7,
                    }
                    result.mentions.append(mention)
                    resolved = resolved.replace(pronoun, antecedent, 1)
                    result.resolution_count += 1

        result.resolved_text = resolved
        return result

    def detect_topic_switch(
        self, current_text: str, history: list[dict], threshold: float = 0.3
    ) -> TopicSwitchResult:
        """话题切换检测"""
        if not history:
            topic = self._extract_topic(current_text)
            return TopicSwitchResult(
                switch_type=TopicSwitchType.CONTINUATION.value,
                current_topic=topic,
                topic_keywords=self._extract_keywords(current_text)[:5],
                confidence=0.5,
                distance_score=0,
            )

        # 提取当前话题
        current_topic = self._extract_topic(current_text)
        current_keywords = set(self._extract_keywords(current_text))

        # 提取历史话题 (最近 5 条)
        history_keywords: set[str] = set()
        last_topic = ""
        for msg in history[-5:]:
            history_keywords.update(self._extract_keywords(msg.get("content", "")))
            t = self._extract_topic(msg.get("content", ""))
            if t:
                last_topic = t

        # 计算话题距离 (Jaccard 距离)
        if current_keywords and history_keywords:
            intersection = current_keywords & history_keywords
            union = current_keywords | history_keywords
            similarity = len(intersection) / max(len(union), 1)
            distance = 1.0 - similarity
        else:
            distance = 0.5

        # 判断切换类型
        if distance < threshold * 0.5:
            switch_type = TopicSwitchType.CONTINUATION.value
        elif distance < threshold:
            switch_type = TopicSwitchType.SOFT_SWITCH.value
        elif current_topic == last_topic and distance >= threshold:
            switch_type = TopicSwitchType.RETURN.value
        else:
            switch_type = TopicSwitchType.HARD_SWITCH.value

        return TopicSwitchResult(
            switch_type=switch_type,
            previous_topic=last_topic,
            current_topic=current_topic,
            confidence=round(min(1.0, distance + 0.3), 3),
            topic_keywords=list(current_keywords)[:5],
            distance_score=round(distance, 3),
        )

    def _extract_topic(self, text: str) -> str:
        """提取话题标签"""
        text_lower = text.lower()
        scores: dict[str, int] = defaultdict(int)
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[topic] += 1
        if scores:
            return max(scores, key=scores.get)
        return "general"

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词"""
        text_lower = text.lower()
        # 中文: 2-6 字词组
        cn_words = re.findall(r'[\u4e00-\u9fff]{2,6}', text_lower)
        # 英文: 按空格分割
        en_words = re.findall(r'[a-z_][a-z0-9_]{1,30}', text_lower)
        all_words = cn_words + en_words
        # 过滤停用词
        return [w for w in all_words if w not in self.STOP_WORDS and len(w) >= 2]

    def _extract_entities(self, text: str) -> list[dict]:
        """简单实体提取"""
        entities = []
        # 数字
        for m in re.finditer(r'\b\d+\.?\d*\b', text):
            entities.append({"text": m.group(), "type": "NUMBER", "start": m.start(), "end": m.end()})
        # URL
        for m in re.finditer(r'https?://\S+', text):
            entities.append({"text": m.group(), "type": "URL", "start": m.start(), "end": m.end()})
        # 邮箱
        for m in re.finditer(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b', text):
            entities.append({"text": m.group(), "type": "EMAIL", "start": m.start(), "end": m.end()})
        # 文件名
        for m in re.finditer(r'[\w./\\-]+\.(py|js|ts|java|go|rs|yaml|json|md|txt)', text):
            entities.append({"text": m.group(), "type": "FILE", "start": m.start(), "end": m.end()})
        return entities


# ============================================================
# 主服务
# ============================================================

class DialogueEnhancementService:
    """
    对话理解增强服务

    - 意图识别: 基于规则/正则, 支持 8 类意图
    - 共指消解: 代词→先行词替换, 基于上下文窗口
    - 话题切换: Jaccard 距离, 3 级切换检测
    - 上下文质量: 4 维度评分 (意图一致性/话题连贯性/共指覆盖/完整度)
    - 可扩展: 通过 set_nlp_fn() 注入外部 NLP 模型
    """

    def __init__(self, context_window: int = 20):
        self._nlp = RuleBasedNLP()
        self._external_nlp_fn: Optional[Callable] = None
        self._dialogue_history: dict[str, list[DialogueTurn]] = defaultdict(list)
        self._context_window = context_window

    def set_nlp_fn(self, fn: Callable):
        """注入外部 NLP 函数 (async fn(text, context) -> dict)"""
        self._external_nlp_fn = fn

    # ----------------------------------------------------------
    # 意图识别
    # ----------------------------------------------------------

    async def detect_intent(self, text: str, session_id: str = "") -> dict:
        """识别用户意图"""
        if self._external_nlp_fn:
            try:
                result = await self._external_nlp_fn(text, [])
                return result
            except Exception as e:
                logger.warning("外部 NLP 调用失败, 回退到规则模式: %s", e)

        result = self._nlp.detect_intent(text)

        # 记录到对话历史
        if session_id:
            turn = DialogueTurn(
                role="user",
                content=text,
                timestamp=time.time(),
                intent=result,
            )
            self._dialogue_history[session_id].append(turn)
            self._trim_history(session_id)

        return {
            "text": result.text,
            "intent": result.intent,
            "confidence": result.confidence,
            "entities": result.entities,
            "keywords": result.keywords,
        }

    async def detect_intent_batch(self, texts: list[str]) -> list[dict]:
        """批量意图识别"""
        return [await self.detect_intent(t) for t in texts]

    # ----------------------------------------------------------
    # 共指消解
    # ----------------------------------------------------------

    async def resolve_coreference(
        self, text: str, session_id: str = ""
    ) -> dict:
        """共指消解"""
        history = []
        if session_id:
            turns = self._dialogue_history.get(session_id, [])
            history = [{"content": t.content, "role": t.role} for t in turns[-self._context_window:]]

        if self._external_nlp_fn:
            try:
                result = await self._external_nlp_fn(text, history)
                return result
            except Exception as e:
                logger.warning("外部 NLP 共指消解失败: %s", e)

        result = self._nlp.resolve_coreference(text, history)
        return {
            "original_text": result.original_text,
            "resolved_text": result.resolved_text,
            "mentions": result.mentions,
            "resolution_count": result.resolution_count,
        }

    # ----------------------------------------------------------
    # 话题切换检测
    # ----------------------------------------------------------

    async def detect_topic_switch(
        self, text: str, session_id: str = "", threshold: float = 0.3
    ) -> dict:
        """话题切换检测"""
        history = []
        if session_id:
            turns = self._dialogue_history.get(session_id, [])
            history = [{"content": t.content} for t in turns[-self._context_window:]]

        result = self._nlp.detect_topic_switch(text, history, threshold)

        # 记录话题到历史
        if session_id:
            for turn in reversed(self._dialogue_history.get(session_id, [])):
                if not turn.topic:
                    turn.topic = result.previous_topic or result.current_topic
                    break

        return {
            "switch_type": result.switch_type,
            "previous_topic": result.previous_topic,
            "current_topic": result.current_topic,
            "confidence": result.confidence,
            "topic_keywords": result.topic_keywords,
            "distance_score": result.distance_score,
        }

    # ----------------------------------------------------------
    # 上下文质量评估
    # ----------------------------------------------------------

    async def evaluate_context_quality(self, session_id: str) -> dict:
        """评估对话上下文质量"""
        turns = self._dialogue_history.get(session_id, [])
        if not turns:
            return {
                "overall_score": 0,
                "issues": ["无对话历史"],
                "suggestions": ["开始对话以获取质量评估"],
            }

        quality = ContextQuality()
        issues = []
        suggestions = []

        # 1. 意图一致性
        user_intents = [t.intent for t in turns if t.role == "user" and t.intent]
        if user_intents:
            intent_counts = defaultdict(int)
            for intent in user_intents:
                intent_counts[intent.intent] += 1
            dominant = max(intent_counts, key=intent_counts.get)
            consistency = intent_counts[dominant] / len(user_intents)
            quality.intent_consistency = round(consistency * 100, 1)
        else:
            quality.intent_consistency = 50.0

        # 2. 话题连贯性
        topic_distances = []
        for i in range(1, len(turns)):
            if turns[i].content and turns[i - 1].content:
                kw1 = set(self._nlp._extract_keywords(turns[i - 1].content))
                kw2 = set(self._nlp._extract_keywords(turns[i].content))
                if kw1 and kw2:
                    intersection = kw1 & kw2
                    union = kw1 | kw2
                    topic_distances.append(len(intersection) / max(len(union), 1))
        if topic_distances:
            avg_coherence = sum(topic_distances) / len(topic_distances)
            quality.topic_coherence = round(avg_coherence * 100, 1)
            if avg_coherence < 0.2:
                issues.append("话题连贯性较低, 用户可能频繁切换话题")
                suggestions.append("考虑总结之前的讨论要点, 保持话题聚焦")
        else:
            quality.topic_coherence = 50.0

        # 3. 共指消解覆盖
        pronoun_turns = 0
        resolved_turns = 0
        for t in turns:
            if t.role == "user" and t.content:
                text_lower = t.content.lower()
                has_pronouns = any(p in text_lower for p in ["它", "他", "她", "这个", "那个", "it", "this", "that", "they"])
                if has_pronouns:
                    pronoun_turns += 1
        if pronoun_turns > 0:
            quality.coreference_resolution = max(0, 100 - pronoun_turns * 10)
        else:
            quality.coreference_resolution = 100.0

        # 4. 上下文完整度
        total_turns = len(turns)
        if total_turns < 3:
            quality.context_completeness = total_turns * 20
            suggestions.append("对话刚开始, 随着对话深入质量评估会更准确")
        elif total_turns < 10:
            quality.context_completeness = 60 + (total_turns - 3) * 5
        else:
            quality.context_completeness = min(100, 60 + total_turns)

        # 综合评分
        quality.overall_score = round(
            quality.intent_consistency * 0.3
            + quality.topic_coherence * 0.3
            + quality.coreference_resolution * 0.2
            + quality.context_completeness * 0.2,
            1,
        )

        # 问题检测
        if quality.intent_consistency < 50:
            issues.append("意图频繁切换, 可能导致模型理解混乱")
        if quality.topic_coherence < 30:
            issues.append("话题频繁跳跃, 建议分多次对话处理不同主题")

        quality.issues = issues
        quality.suggestions = suggestions

        return {
            "overall_score": quality.overall_score,
            "intent_consistency": quality.intent_consistency,
            "topic_coherence": quality.topic_coherence,
            "coreference_resolution": quality.coreference_resolution,
            "context_completeness": quality.context_completeness,
            "turns_analyzed": total_turns,
            "issues": quality.issues,
            "suggestions": quality.suggestions,
        }

    # ----------------------------------------------------------
    # 完整增强管道
    # ----------------------------------------------------------

    async def enhance_message(
        self, text: str, session_id: str = ""
    ) -> dict:
        """
        完整对话增强管道:
        1. 意图识别
        2. 共指消解
        3. 话题切换检测
        4. 返回增强后的文本 + 元数据
        """
        # 1. 意图
        intent = await self.detect_intent(text, session_id)

        # 2. 共指消解
        coref = await self.resolve_coreference(text, session_id)

        # 3. 话题检测
        topic = await self.detect_topic_switch(text, session_id)

        # 4. 增强后的文本
        enhanced_text = coref.get("resolved_text", text)

        return {
            "original_text": text,
            "enhanced_text": enhanced_text,
            "intent": intent,
            "coreference": coref,
            "topic_switch": topic,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ----------------------------------------------------------
    # 会话管理
    # ----------------------------------------------------------

    def clear_session(self, session_id: str):
        """清除会话历史"""
        if session_id in self._dialogue_history:
            del self._dialogue_history[session_id]

    def get_session_summary(self, session_id: str) -> dict:
        """获取会话摘要"""
        turns = self._dialogue_history.get(session_id, [])
        if not turns:
            return {"total_turns": 0}

        intents = [t.intent.intent for t in turns if t.intent]
        topics = [t.topic for t in turns if t.topic]
        intent_dist = defaultdict(int)
        for i in intents:
            intent_dist[i] += 1

        return {
            "total_turns": len(turns),
            "intent_distribution": dict(intent_dist),
            "dominant_topic": max(set(topics), key=topics.count) if topics else "general",
            "unique_topics": list(set(topics)),
            "first_turn": turns[0].content[:100] if turns else "",
            "last_turn": turns[-1].content[:100] if turns else "",
        }

    def list_sessions(self) -> list[dict]:
        """列出活跃会话"""
        return [
            {"session_id": sid, "turns": len(turns)}
            for sid, turns in self._dialogue_history.items()
        ]

    def _trim_history(self, session_id: str):
        """裁剪历史"""
        turns = self._dialogue_history.get(session_id, [])
        if len(turns) > self._context_window * 2:
            self._dialogue_history[session_id] = turns[-self._context_window * 2:]


# 全局实例
_dialogue_enhancement_service: Optional[DialogueEnhancementService] = None


def get_dialogue_enhancement_service() -> DialogueEnhancementService:
    global _dialogue_enhancement_service
    if _dialogue_enhancement_service is None:
        _dialogue_enhancement_service = DialogueEnhancementService()
    return _dialogue_enhancement_service
