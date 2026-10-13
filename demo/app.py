import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]

def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

DOCS = load_json("data/documents.json")
USERS = load_json("data/users.json")
INTERACTIONS = load_json("data/interactions.json")

st.set_page_config(page_title="Персонализированный корпоративный поиск", layout="wide")
st.title("Персонализированный корпоративный поиск")
st.caption("Демонстратор MVP · синтетические данные · лексическое ранжирование")

with st.sidebar:
    st.header("Профиль сотрудника")
    user_names = {u["name"]: u for u in USERS}
    selected_name = st.selectbox("Пользователь", list(user_names))
    user = user_names[selected_name]
    st.write(f"**Роль:** {user['role']}")
    st.write(f"**Подразделение:** {user['team']}")
    query = st.text_input("Поисковый запрос", "лимиты кредитного риска")
    st.divider()
    st.write("**Веса персонализированного ранжирования**")
    w_text = st.slider("Текстовая релевантность", 0.0, 1.0, 0.50, 0.05)
    w_role = st.slider("Соответствие роли", 0.0, 1.0, 0.20, 0.05)
    w_team = st.slider("Соответствие подразделению", 0.0, 1.0, 0.15, 0.05)
    w_history = st.slider("История взаимодействий", 0.0, 1.0, 0.15, 0.05)

st.info("Права доступа проверяются до ранжирования. Персонализация меняет порядок доступных документов, но не расширяет доступ.")

def terms(text):
    return [t.lower() for t in re.findall(r"[\w-]+", text, flags=re.UNICODE) if len(t) > 1]

def normalized_lexical(query_text, doc):
    q = set(terms(query_text))
    if not q:
        return 0.0
    body = " ".join([doc["title"], doc["text"], " ".join(doc.get("tags", []))])
    d = set(terms(body))
    return len(q & d) / len(q)

def access_allowed(doc, person):
    return person["team"] in doc["access"] or person["role"] == "executive" or "executive" in doc["access"] and person["role"] == "executive"

def history_fit(doc, person):
    events = [e for e in INTERACTIONS if e["user_id"] == person["id"] and e["document_id"] == doc["id"]]
    return 1.0 if events else 0.0

def score_row(doc, person, query_text):
    text_score = normalized_lexical(query_text, doc)
    role_score = 1.0 if person["role"] in doc.get("roles", []) else 0.0
    team_score = 1.0 if person["team"] == doc["department"].lower().replace(" ", "_") or person["team"] in doc["access"] else 0.0
    history_score = history_fit(doc, person)
    weights = [w_text, w_role, w_team, w_history]
    total_weight = sum(weights)
    personal_score = 0.0 if total_weight == 0 else (
        w_text * text_score + w_role * role_score + w_team * team_score + w_history * history_score
    ) / total_weight
    return {
        "ID": doc["id"], "Документ": doc["title"], "Подразделение-владелец": doc["department"],
        "Текст": text_score, "Роль": role_score, "Подразделение": team_score,
        "История": history_score, "Базовый балл": text_score, "Персональный балл": personal_score,
        "Обновлён": doc["updated"], "_doc": doc
    }

accessible_docs = [d for d in DOCS if access_allowed(d, user)]
rows = [score_row(d, user, query) for d in accessible_docs]
base = sorted(rows, key=lambda r: (r["Базовый балл"], r["Обновлён"]), reverse=True)
personal = sorted(rows, key=lambda r: (r["Персональный балл"], r["Текст"], r["Обновлён"]), reverse=True)

left, right = st.columns(2)
with left:
    st.subheader("Базовая выдача")
    st.caption("Сортировка по доле слов запроса, найденных в документе.")
    st.dataframe(pd.DataFrame([{k:v for k,v in r.items() if not k.startswith("_") and k not in ("Персональный балл",)} for r in base]), use_container_width=True, hide_index=True)
with right:
    st.subheader("Персонализированная выдача")
    st.caption("Текстовая релевантность + роль + подразделение + история.")
    st.dataframe(pd.DataFrame([{k:v for k,v in r.items() if not k.startswith("_") and k not in ("Базовый балл",)} for r in personal]), use_container_width=True, hide_index=True)

st.subheader("Почему документ получил такой балл?")
if personal:
    chosen = st.selectbox("Документ", [r["Документ"] for r in personal])
    selected = next(r for r in personal if r["Документ"] == chosen)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Текст", f'{selected["Текст"]:.2f}')
    m2.metric("Роль", f'{selected["Роль"]:.2f}')
    m3.metric("Подразделение", f'{selected["Подразделение"]:.2f}')
    m4.metric("История", f'{selected["История"]:.2f}')
    st.write(f"**Дата обновления:** {selected['Обновлён']}")
    st.write(f"**Краткое содержание:** {selected['_doc']['text']}")
else:
    st.warning("Нет документов, доступных выбранному профилю.")

with st.expander("Методика и ограничения"):
    st.markdown("""
    - Текстовый балл — доля уникальных слов запроса, найденных в заголовке, тексте или тегах документа. Это лексический baseline, не эмбеддинги.
    - Баллы роли, подразделения и истории — демонстрационные бинарные признаки.
    - Весовые коэффициенты можно менять в боковой панели; это параметры демонстратора, а не эмпирически обученная модель.
    - Набор документов и профилей синтетический. Перед промышленным применением нужны интеграция с источниками, проверка ACL и оценка качества на размеченных запросах.
    """)
