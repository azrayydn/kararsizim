"""Short, friendly commentary on a poll's results.

This is plain rule-based text (no language model): it only looks at the vote counts.
Keeping it in one small function means it can later be swapped for a real AI call.
"""

NAME_LIMIT = 28


def _short(text, limit=NAME_LIMIT):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _quoted(row):
    return f"“{_short(row['option'].text)}”"


def summarize(rows, total, has_voted, closed=False):
    """rows: list of dicts with option, count, pct, is_mine. Returns a dict or None.

    closed=True means a finished Acil Karar: the wording says the vote is over.
    """
    if total == 0 or len(rows) < 2:
        return None

    ranked = sorted(rows, key=lambda row: (-row["count"], row["option"].position))
    first, second = ranked[0], ranked[1]
    leaders = [row for row in rows if row["count"] == first["count"]]
    gap = (first["count"] - second["count"]) * 100 / total  # percentage points

    if total < 3 and closed:
        mood, emoji = "Az oyla kapandı", "🕊️"
        text = f"Süre doldu ama sadece {total} oy gelmiş. Yorum yapmak için biraz erken."
    elif total < 3:
        mood, emoji = "Isınıyoruz", "🌱"
        text = f"Daha yeni başladık, şu ana kadar {total} oy var. Yorum yapmak için biraz daha oy lazım."
    elif first["count"] == total:
        mood, emoji = "Oybirliği", "🎉"
        text = f"Oybirliği! Herkes {_quoted(first)} demiş."
    elif len(leaders) >= 2:
        mood, emoji = "Tam beraberlik", "⚖️"
        if len(leaders) == 2:
            text = (
                f"{_quoted(leaders[0])} ile {_quoted(leaders[1])} tam başa baş, "
                f"ikisi de %{first['pct']} civarında. Bu sefer kararsızlık haklıymış."
            )
        else:
            text = "Birden fazla seçenek eşit oyda. Bu anket gerçekten kararsız bırakıyor."
    elif len(rows) >= 4 and first["pct"] < 40:
        mood, emoji = "Fikirler dağınık", "🧭"
        text = (
            f"Herkes başka yöne çekiyor: en yüksek oy bile %{first['pct']} "
            f"({_quoted(first)}). Net bir cevap çıkmamış."
        )
    elif gap >= 20:
        mood, emoji = "Net karar", "🏆"
        text = (
            f"Net bir fark var: {_quoted(first)} %{first['pct']} ile önde, "
            f"{_quoted(second)} %{second['pct']}'de kalmış."
        )
    elif gap < 10:
        mood, emoji = "Kıran kırana", "🔥"
        diff = first["count"] - second["count"]
        how_close = f"sadece {diff} oy fark var" if diff <= 3 else f"sadece %{round(gap)} fark var"
        text = f"Kıran kırana! {_quoted(first)} ile {_quoted(second)} arasında {how_close}."
    else:
        mood, emoji = "Önde ama kesin değil", "👀"
        text = (
            f"{_quoted(first)} %{first['pct']} ile önde ama {_quoted(second)} "
            f"%{second['pct']} ile peşinde, hâlâ dönebilir."
        )

    if closed and total >= 3:
        text = "Süre doldu! " + text

    personal = ""
    if has_voted and total >= 3:
        mine = next((row for row in rows if row["is_mine"]), None)
        if mine is not None:
            if mine["count"] == first["count"]:
                personal = "Sen de çoğunluğun yanındasın 🤝"
            else:
                personal = "Sen biraz farklı düşünenlerdensin, bu da güzel 😎"

    return {
        "mood": mood,
        "emoji": emoji,
        "text": text,
        "personal": personal,
        "basis": f"{total} oyla kapandı" if closed else f"{total} oya göre",
    }
