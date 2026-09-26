"""用 Claude 把當日數據寫成簡短的盤勢解讀。失敗時回傳 None，不影響報告寄送。"""
import json
import logging
import os
from typing import Optional

import anthropic

from .models import DailyReport

log = logging.getLogger(__name__)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")

SYSTEM_PROMPT = """你是台股盤後分析助理，讀者是一般投資人。
根據使用者提供的當日盤後數據（JSON），用繁體中文寫 3～5 句盤勢摘要：
- 先講大盤表現與量能，再講法人現貨動向、台指期籌碼（外資未平倉淨額與增減）、新台幣匯率、P/C Ratio 與融資融券變化中值得注意的訊號。
- news 欄位是當日新聞標題，可用來說明市場背景，但只能引用標題中的資訊。
- 只根據提供的數據與新聞標題描述與解讀，不要編造未提供的數字或事件。
- 不給任何買賣建議或價位預測。
- 直接輸出純文字段落，不要標題、條列或 Markdown。

單位說明：金額為新台幣「億元」；期貨未平倉為「口」；融券為「張」；P/C Ratio 為百分比；usd_twd 為 1 美元兌新台幣，數字變大代表台幣貶值。"""


def generate_summary(report: DailyReport) -> Optional[str]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.info("未設定 ANTHROPIC_API_KEY，略過 AI 摘要")
        return None

    client = anthropic.Anthropic()
    data = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": "medium"},
            # 若主模型因安全分類器拒答，由伺服器自動改用建議的備援模型
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"今日盤後數據：\n{data}"}],
        )
    except anthropic.AuthenticationError:
        log.error("ANTHROPIC_API_KEY 無效")
        return None
    except anthropic.RateLimitError:
        log.warning("Claude API 速率限制，略過 AI 摘要")
        return None
    except anthropic.APIStatusError as e:
        log.warning("Claude API 錯誤 %s：%s", e.status_code, e.message)
        return None
    except anthropic.APIConnectionError:
        log.warning("無法連線到 Claude API，略過 AI 摘要")
        return None

    if response.stop_reason == "refusal":
        log.warning("Claude 拒絕產生摘要")
        return None

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return text or None
