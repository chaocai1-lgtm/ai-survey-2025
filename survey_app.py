import streamlit as st
from neo4j import GraphDatabase
from pyecharts import options as opts
from pyecharts.charts import Bar, Pie
from streamlit_echarts import st_pyecharts
import pandas as pd
import datetime
import time 

# ================= 1. 配置与连接 =================
try:
    if st.secrets and "NEO4J_URI" in st.secrets:
        URI = st.secrets["NEO4J_URI"]
        AUTH = ("neo4j", st.secrets["NEO4J_PASSWORD"])
        ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin888")
    else:
        raise Exception("No secrets config")
except Exception:
    URI = "neo4j+ssc://7eb127cc.databases.neo4j.io"
    AUTH = ("neo4j", "wE7pV36hqNSo43mpbjTlfzE7n99NWcYABDFqUGvgSrk")
    ADMIN_PWD = "admin888"

# ================= 2. 问卷题目定义 =================
QUESTIONS = {
    "q1": {"title": "1. 您目前对AI工具（如豆包、ChatGPT等）的了解和使用程度是？", "type": "single", "options": ["A. 完全不了解", "B. 听说过，但未尝试", "C. 偶尔尝试，未应用", "D. 经常使用，辅助工作", "E. 非常熟练"]},
    "q2": {"title": "2. 您最希望AI帮您解决哪类问题？（多选）", "type": "multi", "options": ["A. 教学设计与教案", "B. 课件与素材制作", "C. 文档处理与办公效率", "D. 学生评价与作业批改", "E. 科研辅助与数据分析"]},
    "q3": {"title": "3. 您知道或使用过哪些类型的AI工具？（多选）", "type": "multi", "options": ["A. 语言大模型类", "B. 绘画设计类", "C. PPT生成类", "D. 视频生成类", "E. 办公辅助类"]},
    "q4": {"title": "4. 【大模型专项】您具体了解或使用过哪些大语言模型？（多选）", "type": "multi", "options": ["A. ChatGPT", "B. Claude", "C. Gemini", "D. Copilot", "E. 文心一言", "F. 通义千问", "G. Kimi", "H. 智谱清言", "I. 讯飞星火", "J. 豆包", "K. 腾讯混元", "L. DeepSeek", "M. 海螺AI", "N. 天工AI", "O. 百川智能"]},
    "q5": {"title": "5. 使用AI工具时，您遇到的最大困难是什么？", "type": "single", "options": ["A. 不知道好工具", "B. 不会写提示词", "C. 担心准确性/版权", "D. 操作太复杂", "E. 缺乏应用场景"]},
    "q6": {"title": "6. 您对本次AI培训最期待的收获是什么？", "type": "single", "options": ["A. 了解AI概念趋势", "B. 掌握实用工具", "C. 学习写提示词", "D. 看教学案例", "E. 现场实操指导"]}
}

# ================= 3. 后端逻辑 =================
class SurveyBackend:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(URI, auth=AUTH)
            self.driver.verify_connectivity()
        except Exception as e:
            st.error(f"❌ 数据库连接失败: {e}")

    def close(self):
        if hasattr(self, 'driver'): self.driver.close()

    def submit_response(self, name, answers):
        with self.driver.session() as session:
            query = """CREATE (r:SurveyResponse {name: $name, submitted_at: datetime(), q1: $q1, q2: $q2, q3: $q3, q4: $q4, q5: $q5, q6: $q6})"""
            session.run(query, name=name, **answers)

    def get_all_data(self):
        with self.driver.session() as session:
            result = session.run("MATCH (r:SurveyResponse) RETURN r ORDER BY r.submitted_at DESC")
            data = [dict(record['r']) for record in result]
            for d in data:
                if 'submitted_at' in d:
                    d['submitted_at'] = d['submitted_at'].iso_format().split('.')[0].replace('T', ' ')
            return data

    def reset_database(self):
        with self.driver.session() as session:
            session.run("MATCH (r:SurveyResponse) DETACH DELETE r")

# ================= 4. 可视化组件 =================
def plot_pie(df, col, title):
    if df.empty: return None
    counts = df[col].value_counts()
    data_pair = [list(z) for z in zip(counts.index.tolist(), counts.values.tolist())]
    return (Pie().add("", data_pair, radius=["35%", "60%"]).set_global_opts(title_opts=opts.TitleOpts(title=title, pos_left="center"), legend_opts=opts.LegendOpts(orient="vertical", pos_left="left", type_="scroll")).set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)")))

def plot_bar(df, col, title):
    if df.empty: return None
    all_options = [item for sublist in df[col] for item in (sublist if isinstance(sublist, list) else [sublist])]
    if not all_options: return None
    counts = pd.Series(all_options).value_counts().sort_values(ascending=True)
    return (Bar().add_xaxis(counts.index.tolist()).add_yaxis("人数", counts.values.tolist(), color="#5470c6").reversal_axis().set_global_opts(title_opts=opts.TitleOpts(title=title), xaxis_opts=opts.AxisOpts(name="人数"), yaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(interval=0, formatter=lambda x: x.split('.')[0]))).set_series_opts(label_opts=opts.LabelOpts(position="right")))

# ================= 5. 主程序界面 =================
st.set_page_config(page_title="AI 调研问卷", page_icon="📝", layout="wide")
app = SurveyBackend()

# ✨✨✨ 核心修复：Session状态初始化 ✨✨✨
if 'admin_auth' not in st.session_state:
    st.session_state['admin_auth'] = False

with st.sidebar:
    st.title("📝 问卷系统")
    role = st.radio("当前身份", ["👨‍🎓 我是学生 (填报)", "👩‍🏫 教师后台 (查看)"])
    
    # ✨✨✨ 核心修复：更稳健的登录逻辑 ✨✨✨
    if role == "👩‍🏫 教师后台 (查看)":
        if not st.session_state['admin_auth']:
            # 未登录状态：显示输入框和按钮
            pwd = st.text_input("请输入管理密码", type="password")
            if st.button("🔐 确认登录"):
                if pwd == ADMIN_PWD:
                    st.session_state['admin_auth'] = True
                    st.success("登录成功")
                    time.sleep(0.5)
                    st.rerun() # 立即刷新，进入已登录状态
                else:
                    st.error("密码错误")
        else:
            # 已登录状态：显示退出按钮
            st.success("✅ 管理员已登录")
            if st.button("退出登录"):
                st.session_state['admin_auth'] = False
                st.rerun()

# --- 学生填报 ---
if role == "👨‍🎓 我是学生 (填报)":
    st.header("🤖 AI使用情况课前调研问卷")
    st.markdown("同学你好！请填写以下问卷，带 * 号为必选。")
    st.markdown("---")

    with st.form("survey_form"):
        st.subheader("基本信息")
        name = st.text_input("请输入您的姓名 *", placeholder="必填")

        st.subheader("问卷内容")
        def multi_choice_question(question_key):
            q_info = QUESTIONS[question_key]
            st.markdown(f"**{q_info['title']}**")
            selected_options = []
            for option in q_info["options"]:
                if st.checkbox(option, key=f"{question_key}_{option}"):
                    selected_options.append(option)
            return selected_options

        a1 = st.radio(QUESTIONS["q1"]["title"] + " *", QUESTIONS["q1"]["options"], index=None, horizontal=True)
        a2 = multi_choice_question("q2")
        a3 = multi_choice_question("q3")
        a4 = multi_choice_question("q4")
        a5 = st.radio(QUESTIONS["q5"]["title"] + " *", QUESTIONS["q5"]["options"], index=None)
        a6 = st.radio(QUESTIONS["q6"]["title"] + " *", QUESTIONS["q6"]["options"], index=None)

        st.markdown("---")
        submitted = st.form_submit_button("✅ 提交问卷", type="primary", use_container_width=True)

        if submitted:
            if not name.strip(): st.error("⚠️ 姓名不能为空！")
            elif a1 is None: st.error("⚠️ 第1题尚未选择！")
            elif a5 is None: st.error("⚠️ 第5题尚未选择！")
            elif a6 is None: st.error("⚠️ 第6题尚未选择！")
            else:
                answers = {"q1": a1, "q2": a2, "q3": a3, "q4": a4, "q5": a5, "q6": a6}
                with st.spinner("提交中..."): app.submit_response(name.strip(), answers)
                st.success(f"🎉 提交成功！谢谢 {name.strip()}。"); st.balloons()

# --- 教师后台 ---
elif role == "👩‍🏫 教师后台 (查看)":
    if st.session_state['admin_auth']:
        st.title("📊 调研结果看板")
        raw_data = app.get_all_data()
        df = pd.DataFrame(raw_data)
        
        col_k1, col_k2, col_k3 = st.columns(3)
        col_k1.metric("已填报人数", len(df))
        col_k2.metric("最新提交", df.iloc[0]['name'] if not df.empty else "-")
        col_k3.metric("刷新时间", datetime.datetime.now().strftime("%H:%M:%S"))
        
        if not df.empty:
            tab1, tab2, tab3 = st.tabs(["📈 图表", "📋 明细", "⚙️ 管理"])
            with tab1:
                c1,c2=st.columns(2); c3,c4=st.columns(2); c5,c6=st.columns(2)
                with c1: st_pyecharts(plot_pie(df,"q1","Q1:熟悉程度"))
                with c2: st_pyecharts(plot_bar(df,"q2","Q2:需求分布"))
                with c3: st_pyecharts(plot_bar(df,"q3","Q3:工具类型"))
                with c4: st_pyecharts(plot_bar(df,"q4","Q4:大模型"))
                with c5: st_pyecharts(plot_pie(df,"q5","Q5:最大困难"))
                with c6: st_pyecharts(plot_pie(df,"q6","Q6:期待收获"))
            with tab2:
                st.dataframe(df, use_container_width=True)
                st.download_button("下载 .csv", df.to_csv(index=False).encode('utf-8-sig'), "data.csv")
            with tab3:
                st.warning("危险区域")
                if st.button("🔴 清空数据库") and st.checkbox("确认清空"):
                    app.reset_database(); st.rerun()
        else: st.info("暂无数据"); st.button("清空 (无数据时)", on_click=app.reset_database)
    else:
        st.warning("🔒 请在左侧输入密码登录")

app.close()
