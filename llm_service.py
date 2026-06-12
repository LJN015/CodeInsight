from settings import get_deepseek_client, get_setting


CODE_QA_SYSTEM_PROMPT = (
    "你是 CodeInsight 的代码库分析助手。"
    "请严格基于检索到的代码上下文回答，不要使用未给出的实现细节。"
    "回答时必须先给出简短结论，然后按调用流程或数据流解释。"
    "每个关键判断都要标注来源文件路径和 chunk 编号。"
    "必须区分类、函数、方法的归属，不要把相邻片段里的逻辑错误归因到其他函数。"
    "如果上下文只能证明一部分，请明确写出“已确认”和“仍缺少的上下文”。"
    "不要因为看到相似名称就推断实现；只有代码片段中出现的逻辑才能作为依据。"
)


README_SUMMARY_SYSTEM_PROMPT = (
    "你是一名资深软件工程师，请根据 GitHub 项目 README 生成中文总结。"
)


def summarize_readme(readme_text):
    readme_text = readme_text[:3000]

    response = get_deepseek_client().chat.completions.create(
        model=get_setting("DEEPSEEK_CHAT_MODEL", "deepseek-chat"),
        messages=[
            {
                "role": "system",
                "content": README_SUMMARY_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"""
请总结下面这个 GitHub 项目。
要求：
1. 用一句话说明项目是做什么的；
2. 总结 3 个核心功能；
3. 说明适合学习哪些技术；
4. 控制在 200 字以内。

README:
{readme_text}
""",
            },
        ],
    )

    return response.choices[0].message.content


def answer_with_llm(question: str, contexts):
    context_text = "\n\n".join(
        f"[{i + 1}] {item['path']}#chunk-{item['chunk_id']}\n{item['content']}"
        for i, item in enumerate(contexts)
    )

    response = get_deepseek_client().chat.completions.create(
        model=get_setting("DEEPSEEK_CHAT_MODEL", "deepseek-chat"),
        messages=[
            {
                "role": "system",
                "content": CODE_QA_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"问题：{question}\n\n"
                    "请按以下结构回答：\n"
                    "1. 结论\n"
                    "2. 源码依据\n"
                    "3. 执行流程\n"
                    "4. 不确定或缺失的部分\n\n"
                    f"检索到的代码上下文：\n{context_text}"
                ),
            },
        ],
    )

    return response.choices[0].message.content


def format_model_error(exc: Exception):
    message = str(exc)

    if "Authentication Fails" in message or "401" in message:
        return "DeepSeek API Key 无效或未正确配置。"

    if "Connection" in message or "timed out" in message:
        return "无法连接 DeepSeek 服务，请检查网络或代理。"

    return message


def build_fallback_answer(question: str, contexts, error_message: str):
    files = []
    for item in contexts:
        label = f"{item['path']}#chunk-{item['chunk_id']}"
        if label not in files:
            files.append(label)

    file_list = "\n".join(f"- {item}" for item in files)

    return (
        "已完成代码检索，但调用 DeepSeek 生成最终回答失败。\n\n"
        f"失败原因：{error_message}\n\n"
        f"你的问题：{question}\n\n"
        "当前检索到的相关代码位置：\n"
        f"{file_list}\n\n"
        "请先检查 DEEPSEEK_API_KEY 是否有效。更新 Key 后重新启动服务，"
        "即可得到完整的 AI 中文解释。"
    )
