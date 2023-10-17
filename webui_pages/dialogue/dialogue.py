import streamlit as st
from webui_pages.utils import *
from streamlit_chatbox import *
from datetime import datetime
from server.chat.search_engine_chat import SEARCH_ENGINES
from typing import List, Dict
import os

chat_box = ChatBox(
    assistant_avatar=os.path.join(
        "img",
        "chatchat_icon_blue_square_v2.png"
    )
)


def get_messages_history(history_len: int) -> List[Dict]:
    def filter(msg):
        '''
        针对当前简单文本对话，只返回每条消息的第一个element的内容
        '''
        content = [x._content for x in msg["elements"] if x._output_method in ["markdown", "text"]]
        return {
            "role": msg["role"],
            "content": content[0] if content else "",
        }

    history = chat_box.filter_history(100000, filter)  # workaround before upgrading streamlit-chatbox.
    user_count = 0
    i = 1
    for i in range(1, len(history) + 1):
        if history[-i]["role"] == "user":
            user_count += 1
            if user_count >= history_len:
                break
    return history[-i:]


def dialogue_page(api: ApiRequest):
    chat_box.init_session()

    with st.sidebar:
        # TODO: 对话模型与会话绑定

        dialogue_mode = st.selectbox("Select Conversation Mode",
                                     ["LLM Conversation",
                                      "Knowledge-base Conversation",
                                      ],
                                     key="dialogue_mode",
                                     )
        history_len = st.number_input("Conversation Rounds：", 0, 10, 3)

        # todo: support history len

        def on_kb_change():
            st.toast(f"Loaded knowledge-base： {st.session_state.selected_kb}")

        if dialogue_mode == "Knowledge-base Conversation":
            with st.expander("Knowledge-base Configuation", True):
                kb_list = api.list_knowledge_bases(no_remote_api=True)
                selected_kb = st.selectbox(
                    "Select Knowledge-base：",
                    kb_list,
                    on_change=on_kb_change,
                    key="selected_kb",
                )
                kb_top_k = st.number_input("Matching knowledge entries (1-20)：", 1, 20, 3)
                score_threshold = st.number_input("Knowledge score threshold：", 0.0, 1.0, float(SCORE_THRESHOLD), 0.01)

    # Display chat messages from history on app rerun

    chat_box.output_messages()

    chat_input_placeholder = "Type here, use Ctrl+Enter to change lines."

    if prompt := st.chat_input(chat_input_placeholder, key="prompt"):
        history = get_messages_history(history_len)
        chat_box.user_say(prompt)
        if dialogue_mode == "LLM Conversation":
            chat_box.ai_say("Processing...")
            text = ""
            r = api.chat_chat(prompt, history)
            for t in r:
                if error_msg := check_error_msg(t): # check whether error occured
                    st.error(error_msg)
                    break
                text += t
                chat_box.update_msg(text)
            chat_box.update_msg(text, streaming=False)  # 更新最终的字符串，去除光标
        elif dialogue_mode == "Knowledge-base Conversation":
            history = get_messages_history(history_len)
            chat_box.ai_say([
                f"Searching knowledge-base `{selected_kb}` ...",
                Markdown("...", in_expander=True, title="Knowledge-base matching results"),
            ])
            text = ""
            for d in api.knowledge_base_chat(prompt, selected_kb, kb_top_k, score_threshold, history):
                if error_msg := check_error_msg(d): # check whether error occured
                    st.error(error_msg)
                text += d["answer"]
                chat_box.update_msg(text, 0)
                chat_box.update_msg("\n\n".join(d["docs"]), 1, streaming=False)
            chat_box.update_msg(text, 0, streaming=False)

    now = datetime.now()
    with st.sidebar:

        cols = st.columns(2)
        export_btn = cols[0]
        if cols[1].button(
                "Clear Conversation",
                use_container_width=True,
        ):
            chat_box.reset_history()
            st.experimental_rerun()

    export_btn.download_button(
        "Export Conversation",
        "".join(chat_box.export2md()),
        file_name=f"{now:%Y-%m-%d %H.%M}_Conversation.md",
        mime="text/markdown",
        use_container_width=True,
    )
