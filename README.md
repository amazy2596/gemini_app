curl -X POST http://127.0.0.1:5000/v1beta/openai/chat/completions `
-H "Content-Type: application/json" `
-d '{
    "model": "gemini-2.5-flash-preview-05-20",
    "messages": [
        {
            "role": "user",
            "content": "你好！你现在能正常工作吗？请简单介绍一下你自己。"
        }
    ]
}'