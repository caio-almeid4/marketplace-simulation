from schemas.agent import AgentConfig
from langchain_openai import ChatOpenAI
from utils.render_template import render_template
from models.market import Market
from langchain_core.messages import AnyMessage

class Agent:
    
    
    def __init__(self, config: AgentConfig):
        self.config = config
        
    def _get_llm(self):
        
        return ChatOpenAI(
            model='gpt-4.1-mini',
            temperature=self.config.temperature,
        )
        
    def _update_messages(self, message: AnyMessage) -> None:
        
        self.config.state['messages'].append(message)
        return None
    
    def _get_internal_memory(self) -> str:
        return render_template('memory', {'internal_monologue': self.config.state['internal_monologue']})
                               
    def run_turn(self, market: Market):
        ...
        
        
        
        
        
        
        
        