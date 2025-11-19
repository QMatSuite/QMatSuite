"""
Command-line interface for QuantumVITAS.

This module provides the CLI entry point: quantumvitas ...
"""

import argparse
import sys
from pathlib import Path
import logging

# TODO: Import core modules when ready
# from quantumvitas.core.models import Project
# from quantumvitas.core.runner import WorkflowRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="quantumvitas",
        description="QuantumVITAS - Quantum Visualization Interactive Toolkit for Ab-initio Simulations"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create project command
    create_parser = subparsers.add_parser("create", help="Create a new project")
    create_parser.add_argument("name", help="Project name")
    create_parser.add_argument("--workspace", type=Path, help="Workspace directory")
    
    # Run workflow command
    run_parser = subparsers.add_parser("run", help="Run a workflow")
    run_parser.add_argument("project", help="Project name")
    run_parser.add_argument("workflow", help="Workflow name")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List projects/workflows")
    list_parser.add_argument("--projects", action="store_true", help="List projects")
    list_parser.add_argument("--workflows", action="store_true", help="List workflows")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # TODO: Implement command handlers
    if args.command == "create":
        logger.info(f"Creating project '{args.name}'")
        # TODO: Implement project creation
        print(f"Project creation not yet implemented: {args.name}")
    
    elif args.command == "run":
        logger.info(f"Running workflow '{args.workflow}' in project '{args.project}'")
        # TODO: Implement workflow execution
        print(f"Workflow execution not yet implemented: {args.project}/{args.workflow}")
    
    elif args.command == "list":
        if args.projects:
            # TODO: List projects
            print("Project listing not yet implemented")
        elif args.workflows:
            # TODO: List workflows
            print("Workflow listing not yet implemented")
        else:
            list_parser.print_help()


if __name__ == "__main__":
    main()

