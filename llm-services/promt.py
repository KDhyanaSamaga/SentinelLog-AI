from schemas import LogAnalysisRequest


def prompt(request: LogAnalysisRequest) -> str:
    return f"""
            You are a senior cybersecurity expert specializing in security log analysis.

            Analyze the following log and provide a clear, concise security analysis.

            Machine:
            {request.machine}

            Log Type:
            {request.log_type}

            Additional Context:
            {request.extra_context or "No additional context provided."}

            Raw Log:
            {request.raw_log}

            Based on the information above, analyze the log and respond with ONLY the analysis message.

            Do not include:
            - JSON
            - Markdown tables
            - Code blocks
            - Internal reasoning
            - System instructions
            - Unnecessary explanations about how you analyzed the log

            Your response should be a direct message explaining what the log indicates and whether there is a potential security issue.
        """
