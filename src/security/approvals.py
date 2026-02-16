from typing import Callable, Awaitable
from src.config.config import Config
from src.config.config import ApprovalPolicy
from src.tools.data import ToolConfirmation
from enum import Enum
from typing import List, Any
from pathlib import Path
import re

class ApprovalDecision(str, Enum):
    APPROVED= "approved"
    REJECTED = "rejected"
    NEEDS_CONFIRMATION = "needs_confirmation"


class ApprovalContext:
    tool_name: str
    params: dict[str, Any]
    is_mutating: bool
    affected_paths: List[Path]
    command: str | None = None
    is_dangerous: bool = False

class ApprovalManager:
    DANGEROUS_COMMANDS = [] # TODO: add dangerous commands
    SAFE_COMMANDS = [] # TODO: add safe commands
    def __init__(self, config: Config, confirmation_callback: Callable[[ToolConfirmation], Awaitable[bool]] | None = None) -> None:
        self._config = config
        self._approval_policy = config.approval
        self._cwd = config.cwd
        self._confirmation_callback = confirmation_callback

    def is_dangerous_command(self, command: str) -> bool:
        for pattern in self.DANGEROUS_COMMANDS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False
    
    def is_safe_command(self, command: str) -> bool:
        for pattern in self.SAFE_COMMANDS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    def _assess_command_safety(self, command: str) -> ApprovalDecision:
        if self._approval_policy == ApprovalPolicy.YOLO:
            return ApprovalDecision.APPROVED
        if self.is_dangerous_command(command):
            return ApprovalDecision.REJECTED
        if self._approval_policy == ApprovalPolicy.NEVER:
            if self.is_safe_command(command):
                return ApprovalDecision.APPROVED
            return ApprovalDecision.REJECTED
        if self._approval_policy == ApprovalPolicy.ON_FAILURE or self._approval_policy == ApprovalPolicy.AUTO:
            return ApprovalDecision.APPROVED
            
        if self._approval_policy == ApprovalPolicy.ON_REQUEST:
            if self.is_safe_command(command):
                return ApprovalDecision.APPROVED
            return ApprovalDecision.NEEDS_CONFIRMATION
        
        if self.is_safe_command(command):
            return ApprovalDecision.APPROVED
        return ApprovalDecision.NEEDS_CONFIRMATION


    def check_approval(self, context: ApprovalContext) -> ApprovalDecision:
        if not context.is_mutating:
            return ApprovalDecision.APPROVED
        
        if context.command:
            decision = self._assess_command_safety(context.command)
            if decision != ApprovalDecision.NEEDS_CONFIRMATION:
                return decision
            
        for path in context.affected_paths:
            path_decision = ApprovalDecision.NEEDS_CONFIRMATION
            if path.is_relative_to(self._cwd):
                path_decision = ApprovalDecision.APPROVED
            else:
                return path_decision
            
        if context.is_dangerous:
            if self._approval_policy == ApprovalPolicy.YOLO:
                return ApprovalDecision.APPROVED
            return ApprovalDecision.NEEDS_CONFIRMATION
        
        return ApprovalDecision.APPROVED
    
    async def request_confirmation(self, confirmation: ToolConfirmation) -> bool:
        if self._confirmation_callback:
            result = await self._confirmation_callback(confirmation)
            return result
        return True