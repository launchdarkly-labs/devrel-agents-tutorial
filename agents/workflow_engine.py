import re
from typing import Dict, List, Any, Optional
from langchain_anthropic import ChatAnthropic
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.redaction import RedactionTool
from tools_impl.reranking import RerankingTool

class WorkflowStep:
    def __init__(self, tool_name: str, condition: Optional[str] = None, required: bool = True):
        self.tool_name = tool_name
        self.condition = condition
        self.required = required

class WorkflowEngine:
    def __init__(self, config):
        self.config = config
        self.tools = self._initialize_tools()
        self.model = ChatAnthropic(model=config.model, temperature=0.1)
        
    def _initialize_tools(self):
        tools = {}
        for tool_name in self.config.allowed_tools:
            if tool_name == "search_v1":
                tools[tool_name] = SearchToolV1()
            elif tool_name == "search_v2":
                tools[tool_name] = SearchToolV2()
            elif tool_name == "redaction":
                tools[tool_name] = RedactionTool()
            elif tool_name == "reranking":
                tools[tool_name] = RerankingTool()
        return tools
    
    def _check_condition(self, condition: str, user_input: str, context: Dict) -> bool:
        """Check if a condition is met"""
        if condition == "contains_pii":
            # Check for email, phone, SSN patterns
            pii_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # email
                r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # phone
                r'\b\d{3}-\d{2}-\d{4}\b'  # SSN
            ]
            return any(re.search(pattern, user_input) for pattern in pii_patterns)
        
        elif condition == "needs_search":
            # Check if query is asking for technical information
            search_indicators = ['help', 'how', 'what', 'explain', 'definition', 'algorithm', 'method', 'technique', 'implementation', 'theory', 'concept']
            return any(word in user_input.lower() for word in search_indicators)
        
        elif condition == "has_search_results":
            # Check if we have search results in context
            return 'search_results' in context and len(context['search_results']) > 0
        
        elif condition == "multiple_results":
            # Check if we have multiple search results that could benefit from reranking
            return 'search_results' in context and len(context['search_results'].split('\n')) > 3
        
        return True  # Default to true for unknown conditions
    
    async def execute_workflow(self, user_input: str) -> Dict[str, Any]:
        """Execute the multi-step workflow"""
        context = {
            'original_input': user_input,
            'current_text': user_input,
            'tool_calls': [],
            'search_results': '',
            'final_response': ''
        }
        
        # Define workflow steps based on available tools
        steps = self._get_workflow_steps()
        
        # Execute each step
        for step in steps:
            if self._should_execute_step(step, user_input, context):
                result = await self._execute_step(step, context)
                context['tool_calls'].append(step.tool_name)
                
                # Update context based on tool type
                if step.tool_name in ['search_v1', 'search_v2']:
                    context['search_results'] = result
                elif step.tool_name == 'redaction':
                    context['current_text'] = result
                elif step.tool_name == 'reranking':
                    context['search_results'] = result
        
        # Generate final response
        context['final_response'] = await self._generate_final_response(context)
        
        return {
            'response': context['final_response'],
            'tool_calls': context['tool_calls']
        }
    
    def _get_workflow_steps(self) -> List[WorkflowStep]:
        """Define workflow steps based on LaunchDarkly configuration"""
        steps = []
        
        # Step 1: Redaction (if PII detected and redaction available)
        if 'redaction' in self.tools:
            steps.append(WorkflowStep('redaction', condition='contains_pii', required=False))
        
        # Step 2: Search (if search tools available and query needs information)  
        if 'search_v2' in self.tools:
            steps.append(WorkflowStep('search_v2', condition='needs_search', required=False))
        elif 'search_v1' in self.tools:
            steps.append(WorkflowStep('search_v1', condition='needs_search', required=False))
        
        # Step 3: Reranking (if reranking available and we have multiple results)
        if 'reranking' in self.tools:
            steps.append(WorkflowStep('reranking', condition='multiple_results', required=False))
        
        return steps
    
    def _should_execute_step(self, step: WorkflowStep, user_input: str, context: Dict) -> bool:
        """Determine if a workflow step should be executed"""
        if step.condition:
            return self._check_condition(step.condition, user_input, context)
        return step.required
    
    async def _execute_step(self, step: WorkflowStep, context: Dict) -> str:
        """Execute a single workflow step"""
        tool = self.tools[step.tool_name]
        
        if step.tool_name in ['search_v1', 'search_v2']:
            # For search tools, use the current text (potentially cleaned)
            return tool._run(context['current_text'])
        
        elif step.tool_name == 'redaction':
            # For redaction, clean the original input
            return tool._run(context['original_input'])
        
        elif step.tool_name == 'reranking':
            # For reranking, use the search results and original query
            if context['search_results']:
                return tool._run(context['current_text'], context['search_results'])
            return context['search_results']
        
        return "Tool execution failed"
    
    async def _generate_final_response(self, context: Dict) -> str:
        """Generate the final response based on workflow results"""
        
        # Build context for final response
        response_context = []
        
        if 'redaction' in context['tool_calls']:
            response_context.append("I've cleaned any personal information from your message.")
        
        if context['search_results']:
            response_context.append("Based on my search of technical documentation:")
        
        # Create final prompt
        prompt = f"""
        {self.config.instructions}
        
        User question: {context['original_input']}
        
        {"Context: " + " ".join(response_context) if response_context else ""}
        
        {f"Search results: {context['search_results']}" if context['search_results'] else ""}
        
        Please provide a helpful response based on the available information.
        """
        
        response = self.model.invoke(prompt)
        return response.content