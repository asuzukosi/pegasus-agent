import tiktoken

def get_tokenizer(model: str):
    try:
        encoding = tiktoken.encoding_for_model(model)
        return encoding.encode
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
        return encoding.encode
    
def count_tokens(text: str, model: str) -> int:
    tokenizer = get_tokenizer(model)
    if tokenizer:
        return len(tokenizer(text))
    return estimate_tokens(text)

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _truncate_by_chars(text: str, target_tokens: int, suffix: str, model: str) -> str:
    low, high = 0, len(text)
    while low < high:
        mid = (low + high) // 2
        if count_tokens(text[:mid], model) <= target_tokens:
            low = mid
        else:
            high = mid - 1

    return text[:low] + suffix.strip()


def _truncate_by_lines(text: str, target_tokens: int, suffix: str, model: str) -> str:
    lines = text.split("\n")
    result_lines: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line + "\n", model)
        if current_tokens + line_tokens > target_tokens:
            break
        result_lines.append(line)
        current_tokens += line_tokens
    if not result_lines:
        return _truncate_by_chars(text, target_tokens, suffix, model)
    return "\n".join(result_lines) + "\n" + suffix.strip()

def truncate_text(text: str, model: str, max_tokens: int, 
                  suffix: str = "\n...[truncated]", 
                  preserve_lines: bool = True) -> str:
    token_count = count_tokens(text, model)
    if token_count <= max_tokens:
        return text
    suffix_tokens = count_tokens(suffix, model)
    target_tokens = max_tokens - suffix_tokens
    
    if target_tokens <= 0:
        return suffix.strip()
    
    if preserve_lines:
        return _truncate_by_lines(text, target_tokens, suffix, model)