#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复前端 TypeScript 错误"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
SRC_DIR = BASE_DIR / "src"

def fix_conversation_detail():
    """修复 ConversationDetail.tsx"""
    filepath = SRC_DIR / "pages" / "ConversationDetail.tsx"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修复 useWebSocket 导入
    content = content.replace(
        "import { useWebSocket } from '../hooks/useWebSocket'",
        "import { useWebSocketChat } from '../hooks/useWebSocket'"
    )
    
    # 修复函数调用
    content = content.replace(
        "const { sendMessage, cancelMessage, isConnected, attemptReconnect } = useWebSocket({",
        "const { sendMessage, cancelMessage, isConnected, attemptReconnect } = useWebSocketChat({"
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] Fixed: ConversationDetail.tsx")

def fix_model_version():
    """修复 ModelVersionPage.tsx"""
    filepath = SRC_DIR / "pages" / "ModelVersionPage.tsx"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除未使用的导入
    content = content.replace("import { ChevronDown, ChevronUp } from 'lucide-react'", 
                              "import {} from 'lucide-react'")
    content = content.replace("import { useModelTemplateStore } from '../stores/modelConfigStore'", "")
    content = content.replace("import { format } from 'date-fns'", "")
    content = content.replace("import zhCN from 'date-fns/locale/zh-CN'", "")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] Fixed: ModelVersionPage.tsx")

def fix_streaming_chat():
    """修复 StreamingChatPage.tsx"""
    filepath = SRC_DIR / "pages" / "StreamingChatPage.tsx"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除未使用的导入
    content = content.replace("import { Send, User } from 'lucide-react'", 
                              "import {} from 'lucide-react'")
    content = content.replace("import { ChatMessageItem } from '../components/ChatMessage'", "")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] Fixed: StreamingChatPage.tsx")

def main():
    print("=" * 70)
    print("Fixing Frontend TypeScript Errors")
    print("=" * 70)
    
    fix_conversation_detail()
    fix_model_version()
    fix_streaming_chat()
    
    print("\n" + "=" * 70)
    print("Frontend fixes complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()
