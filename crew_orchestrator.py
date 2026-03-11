import os
os.environ['CREWAI_DISABLE_TELEMETRY'] = 'true'
os.environ['OTEL_SDK_DISABLED'] = 'true'

from crewai import Agent, Task, Crew, LLM

llm = LLM(model="ollama/llama3.2:3b", base_url="http://localhost:11434")
coder_llm = LLM(model="ollama/qwen2.5-coder:3b", base_url="http://localhost:11434")

brain_agent = Agent(
    role="JARVIS Brain",
    goal="Answer questions and have intelligent conversations as a British AI butler",
    backstory="You are JARVIS, an incredibly intelligent AI assistant. Formal, concise, always address user as sir.",
    llm=llm,
    verbose=False
)

coding_agent = Agent(
    role="Coding Specialist",
    goal="Write clean, working code for any programming task",
    backstory="You are an expert programmer embedded in JARVIS. Write clean commented code, always address user as sir.",
    llm=coder_llm,
    verbose=False
)

finance_agent = Agent(
    role="Finance Analyst",
    goal="Analyze financial data and give investment insights",
    backstory="You are a financial expert inside JARVIS. Give concise market analysis, address user as sir.",
    llm=llm,
    verbose=False
)

desktop_agent = Agent(
    role="Desktop Automation Specialist",
    goal="Help automate desktop tasks and file management",
    backstory="You are a desktop automation expert inside JARVIS. Help with files and system tasks. Address user as sir.",
    llm=llm,
    verbose=False
)


def run_crew(agent, task_description):
    task = Task(
        description=task_description,
        agent=agent,
        expected_output="A helpful concise response addressing the user as sir"
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    result = crew.kickoff()
    return str(result)


def route_to_crew(intent, user_text):
    if intent == "coding":
        return run_crew(coding_agent, user_text)
    elif intent == "finance":
        return run_crew(finance_agent, user_text)
    elif intent == "desktop":
        return run_crew(desktop_agent, user_text)
    else:
        return run_crew(brain_agent, user_text)