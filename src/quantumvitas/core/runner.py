"""
Workflow runner for executing calculation steps.

This module provides synchronous execution of workflows and steps.
Future versions will support asynchronous execution.
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import logging

from .models import Step, Workflow, Project
from .registry import get_registry

logger = logging.getLogger(__name__)


class WorkflowRunner:
    """
    Synchronous workflow runner.
    
    Executes workflow steps in order, respecting dependencies.
    """
    
    def __init__(self, project: Project):
        """
        Initialize workflow runner.
        
        Args:
            project: Project containing workflows to execute
        """
        self.project = project
        self.registry = get_registry()
        self._stop_requested = False
    
    def run_workflow(self, workflow_name: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Run a complete workflow.
        
        Args:
            workflow_name: Name of workflow to run
            callback: Optional callback function called after each step
                     Signature: callback(step: Step, status: str, result: Dict)
            
        Returns:
            Dictionary with execution results
        """
        workflow = self.project.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_name}' not found")
        
        if not workflow.working_dir:
            workflow.working_dir = self.project.project_dir / workflow.name
        workflow.working_dir.mkdir(parents=True, exist_ok=True)
        
        self._stop_requested = False
        results = {
            "workflow": workflow_name,
            "steps": {},
            "success": True,
            "errors": []
        }
        
        # Get steps in execution order
        ordered_steps = workflow.get_ordered_steps()
        
        for step in ordered_steps:
            if self._stop_requested:
                results["success"] = False
                results["errors"].append("Execution stopped by user")
                break
            
            try:
                step_result = self.run_step(step, workflow.working_dir)
                results["steps"][step.name] = step_result
                
                if callback:
                    callback(step, step_result.get("status", "unknown"), step_result)
                
                if step_result.get("status") == "failed":
                    results["success"] = False
                    results["errors"].append(f"Step '{step.name}' failed")
                    # Optionally stop on first failure
                    # break
                    
            except Exception as e:
                logger.error(f"Error running step '{step.name}': {e}", exc_info=True)
                results["steps"][step.name] = {
                    "status": "failed",
                    "error": str(e)
                }
                results["success"] = False
                results["errors"].append(f"Step '{step.name}': {str(e)}")
        
        return results
    
    def run_step(self, step: Step, working_dir: Path) -> Dict[str, Any]:
        """
        Run a single calculation step.
        
        Args:
            step: Step to execute
            working_dir: Working directory for execution
            
        Returns:
            Dictionary with step execution results
        """
        step.status = "running"
        result = {
            "step": step.name,
            "status": "running",
            "input_file": None,
            "output_file": None,
            "command": None,
            "return_code": None,
            "error": None
        }
        
        try:
            # Get engine for this step
            engine = self.registry.create_engine(step.engine)
            
            # Generate input file
            input_file = engine.generate_input(
                step_type=step.step_type.value,
                input_data=step.input_data,
                working_dir=working_dir,
                input_filename=step.input_file.name if step.input_file else None
            )
            step.input_file = input_file
            result["input_file"] = str(input_file)
            
            # Build command
            command = engine.build_command(
                step_type=step.step_type.value,
                input_file=input_file,
                working_dir=working_dir
            )
            result["command"] = " ".join(command)
            
            # Determine output file
            if step.output_file:
                output_file = working_dir / step.output_file
            else:
                output_filename = engine.get_default_output_filename(
                    step_type=step.step_type.value,
                    input_filename=input_file.name
                )
                output_file = working_dir / output_filename
            step.output_file = output_file
            
            # Execute command
            logger.info(f"Running step '{step.name}': {result['command']}")
            process = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                env=engine.config.environment
            )
            
            result["return_code"] = process.returncode
            
            # Write stdout/stderr to files for transparency
            stdout_file = working_dir / f"{step.name}.stdout"
            stderr_file = working_dir / f"{step.name}.stderr"
            stdout_file.write_text(process.stdout)
            stderr_file.write_text(process.stderr)
            
            if process.returncode == 0:
                step.status = "completed"
                result["status"] = "completed"
                
                # Parse output if possible
                try:
                    parsed = engine.parse_output(output_file, step.step_type.value)
                    result["parsed"] = parsed
                except Exception as e:
                    logger.warning(f"Could not parse output for step '{step.name}': {e}")
            else:
                step.status = "failed"
                result["status"] = "failed"
                result["error"] = process.stderr or "Unknown error"
                logger.error(f"Step '{step.name}' failed with return code {process.returncode}")
            
        except FileNotFoundError as e:
            step.status = "failed"
            result["status"] = "failed"
            result["error"] = f"Executable not found: {e}"
            logger.error(f"Step '{step.name}': {result['error']}")
        except Exception as e:
            step.status = "failed"
            result["status"] = "failed"
            result["error"] = str(e)
            logger.error(f"Step '{step.name}': {e}", exc_info=True)
        
        return result
    
    def stop(self):
        """Request stop of current execution."""
        self._stop_requested = True

