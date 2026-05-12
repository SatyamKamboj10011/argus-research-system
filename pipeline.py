from agents import build_search_agent, build_read_agent, build_writer_chain, build_critic_chain, get_llm

def run_research_pipeline(topic: str, llm) -> dict:

    state = {}

    writer_chain = build_writer_chain(llm)
    critic_chain = build_critic_chain(llm)

    # Search Agent
    print("\n" + "="*50)
    print("SEARCH AGENT WORKING...")
    print("="*50)

    search_agent = build_search_agent(llm)
    search_result = search_agent.invoke({
        "messages": [("user", f"Find the latest and most relevant information on the topic: {topic}")]
    })
    state["search_results"] = search_result['messages'][-1].content
    print("\n Search Results: \n", state["search_results"])

    # Reader Agent
    print("\n" + "="*50)
    print("READER AGENT IS SCRAPING TOP RESOURCES...")
    print("="*50)

    reader_agent = build_read_agent(llm)
    reader_result = reader_agent.invoke({
        "messages": [("user",
                     f"You are a web scraper agent. The search results below contain URLs.\n"
f"You MUST call the scrape_url tool with one of the URLs listed below.\n"
f"Do NOT say you cannot find URLs — they are clearly listed after 'URL:' in each result.\n"
f"Topic: {topic}\n\n"
f"Search Results:\n{state['search_results'][:2000]}"
                     )]
    })
    state["scraped_content"] = reader_result['messages'][-1].content
    print("\n Scraped Content: \n", state["scraped_content"])

    # Writer Chain
    print("\n" + "="*50)
    print("WRITER CHAIN IS CREATING THE RESEARCH REPORT...")
    print("="*50)

    research_combined = (
        f"Search Results: \n{state['search_results']}\n\n"
        f"Scraped Content: \n{state['scraped_content']}"
    )
    state["report"] = writer_chain.invoke({
        "topic": topic,
        "research": research_combined
    })
    print("\n Research Report: \n", state["report"])

    # Critic Chain
    print("\n" + "="*50)
    print("CRITIC CHAIN IS EVALUATING THE RESEARCH REPORT...")
    print("="*50)

    state["feedback"] = critic_chain.invoke({
        "report": state["report"]
    })
    print("\n Critic Feedback: \n", state["feedback"])

    return state


if __name__ == "__main__":
    topic = input("\nEnter a research topic: ")
    llm = get_llm("Groq — Llama 3.3 70B", api_key=None)  # uses .env key by default
    result = run_research_pipeline(topic, llm)