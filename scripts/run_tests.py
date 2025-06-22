#!/usr/bin/env python3
"""
Script para executar diferentes tipos de testes do Fusion Client.

Este script oferece uma interface conveniente para executar testes
com diferentes configurações e cenários.
"""

import os
import sys
import subprocess
import argparse
import time
import json
from pathlib import Path
from typing import List, Optional, Dict, Any


class TestRunner:
    """Runner para diferentes tipos de testes."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent
        self.test_results: Dict[str, Any] = {}
    
    def log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[INFO] {message}")
    
    def run_command(self, cmd: List[str], description: str) -> bool:
        """
        Executar comando e retornar sucesso/falha.
        
        Args:
            cmd: Comando para executar
            description: Descrição do comando
            
        Returns:
            True se comando foi bem-sucedido, False caso contrário
        """
        self.log(f"Running: {description}")
        self.log(f"Command: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=not self.verbose,
                text=True,
                check=True
            )
            
            duration = time.time() - start_time
            self.test_results[description] = {
                "status": "passed",
                "duration": duration,
                "output": result.stdout if not self.verbose else None
            }
            
            print(f"✅ {description} - Passed ({duration:.2f}s)")
            return True
            
        except subprocess.CalledProcessError as e:
            duration = time.time() - start_time
            self.test_results[description] = {
                "status": "failed",
                "duration": duration,
                "error": str(e),
                "output": e.stdout,
                "stderr": e.stderr
            }
            
            print(f"❌ {description} - Failed ({duration:.2f}s)")
            if not self.verbose:
                print(f"Error: {e.stderr}")
            return False
    
    def check_environment(self) -> bool:
        """Verificar se o ambiente está configurado corretamente."""
        print("🔍 Checking environment...")
        
        # Verificar Python
        python_version = sys.version_info
        if python_version < (3, 9):
            print(f"❌ Python 3.9+ required, found {python_version.major}.{python_version.minor}")
            return False
        
        print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # Verificar dependências
        try:
            import pytest
            import httpx
            import pydantic
            import respx
            print("✅ Core dependencies available")
        except ImportError as e:
            print(f"❌ Missing dependency: {e}")
            return False
        
        # Verificar estrutura do projeto
        required_dirs = [
            self.project_root / "tests",
            self.project_root / "tests" / "unit",
            self.project_root / "tests" / "integration",
            self.project_root / "tests" / "fixtures"
        ]
        
        for dir_path in required_dirs:
            if not dir_path.exists():
                print(f"❌ Missing directory: {dir_path}")
                return False
        
        print("✅ Project structure OK")
        return True
    
    def run_unit_tests(self) -> bool:
        """Executar testes unitários."""
        return self.run_command(
            ["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short"],
            "Unit Tests"
        )
    
    def run_integration_tests(self, with_api: bool = False) -> bool:
        """Executar testes de integração."""
        cmd = ["python", "-m", "pytest", "tests/integration/", "-v", "--tb=short"]
        
        if with_api:
            # Verificar se API key está configurada
            if not os.getenv("FUSION_API_KEY"):
                print("⚠️  FUSION_API_KEY not set - skipping real API tests")
                cmd.extend(["-m", "not api"])
            description = "Integration Tests (with API)"
        else:
            cmd.extend(["-m", "not api"])
            description = "Integration Tests (mock only)"
        
        return self.run_command(cmd, description)
    
    def run_langchain_tests(self) -> bool:
        """Executar testes de integração LangChain."""
        return self.run_command(
            ["python", "-m", "pytest", "tests/integration/test_langchain_integration.py", "-v"],
            "LangChain Integration Tests"
        )
    
    def run_crewai_tests(self) -> bool:
        """Executar testes de integração CrewAI."""
        return self.run_command(
            ["python", "-m", "pytest", "tests/integration/test_crewai_integration.py", "-v"],
            "CrewAI Integration Tests"
        )
    
    def run_example_tests(self) -> bool:
        """Executar testes de exemplos da documentação."""
        return self.run_command(
            ["python", "-m", "pytest", "tests/test_examples.py", "-v"],
            "Documentation Examples Tests"
        )
    
    def run_performance_tests(self) -> bool:
        """Executar testes de performance."""
        return self.run_command(
            ["python", "-m", "pytest", "tests/integration/", "-m", "performance", "-v"],
            "Performance Tests"
        )
    
    def run_coverage_tests(self) -> bool:
        """Executar testes com cobertura."""
        return self.run_command(
            [
                "python", "-m", "pytest",
                "tests/unit/", "tests/test_examples.py",
                "--cov=fusion_client",
                "--cov-report=term-missing",
                "--cov-report=html",
                "--cov-fail-under=90"
            ],
            "Coverage Tests"
        )
    
    def run_lint_checks(self) -> bool:
        """Executar verificações de linting."""
        success = True
        
        # Ruff check
        if not self.run_command(
            ["python", "-m", "ruff", "check", "fusion_client/", "tests/"],
            "Ruff Linting"
        ):
            success = False
        
        # MyPy check
        if not self.run_command(
            ["python", "-m", "mypy", "fusion_client/"],
            "MyPy Type Checking"
        ):
            success = False
        
        # Black formatting check
        if not self.run_command(
            ["python", "-m", "black", "--check", "fusion_client/", "tests/"],
            "Black Formatting Check"
        ):
            success = False
        
        return success
    
    def run_security_checks(self) -> bool:
        """Executar verificações de segurança."""
        success = True
        
        # Pip audit (se disponível)
        try:
            subprocess.run(["pip-audit", "--version"], check=True, capture_output=True)
            if not self.run_command(
                ["pip-audit"],
                "Security Audit"
            ):
                success = False
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  pip-audit not available - skipping security audit")
        
        # Bandit (se disponível)
        try:
            subprocess.run(["bandit", "--version"], check=True, capture_output=True)
            if not self.run_command(
                ["bandit", "-r", "fusion_client/", "-f", "txt"],
                "Bandit Security Scan"
            ):
                success = False
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  bandit not available - skipping security scan")
        
        return success
    
    def start_mock_server(self):
        """Iniciar servidor mock em background."""
        self.log("Starting mock server...")
        
        # Script para iniciar servidor
        server_script = """
from tests.testing.mock_server import MockFusionServer
import time
import signal
import sys

server = MockFusionServer()
server.start_background()
print(f"Mock server started at {server.base_url}")

def signal_handler(sig, frame):
    print("Stopping mock server...")
    server.stop_background()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    server.stop_background()
"""
        
        # Salvar script temporário
        script_path = self.project_root / "temp_mock_server.py"
        with open(script_path, "w") as f:
            f.write(server_script)
        
        try:
            # Iniciar servidor
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=self.project_root
            )
            
            # Aguardar servidor iniciar
            time.sleep(2)
            
            return process
            
        finally:
            # Limpar arquivo temporário
            if script_path.exists():
                script_path.unlink()
    
    def generate_report(self) -> str:
        """Gerar relatório de resultados dos testes."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results.values() if r["status"] == "passed")
        failed_tests = total_tests - passed_tests
        total_duration = sum(r["duration"] for r in self.test_results.values())
        
        report = [
            "\n" + "="*60,
            "TEST EXECUTION SUMMARY",
            "="*60,
            f"Total Tests: {total_tests}",
            f"Passed: {passed_tests}",
            f"Failed: {failed_tests}",
            f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "Success Rate: 0%",
            f"Total Duration: {total_duration:.2f}s",
            ""
        ]
        
        if failed_tests > 0:
            report.append("FAILED TESTS:")
            report.append("-" * 20)
            for name, result in self.test_results.items():
                if result["status"] == "failed":
                    report.append(f"❌ {name}")
                    if "error" in result:
                        report.append(f"   Error: {result['error']}")
            report.append("")
        
        report.append("DETAILED RESULTS:")
        report.append("-" * 20)
        for name, result in self.test_results.items():
            status_icon = "✅" if result["status"] == "passed" else "❌"
            report.append(f"{status_icon} {name} ({result['duration']:.2f}s)")
        
        return "\n".join(report)


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Run Fusion Client tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--with-api", action="store_true", help="Include real API tests")
    parser.add_argument("--langchain", action="store_true", help="Run LangChain tests")
    parser.add_argument("--crewai", action="store_true", help="Run CrewAI tests")
    parser.add_argument("--examples", action="store_true", help="Run example tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage")
    parser.add_argument("--lint", action="store_true", help="Run linting checks")
    parser.add_argument("--security", action="store_true", help="Run security checks")
    parser.add_argument("--fast", action="store_true", help="Run fast tests only (unit + examples)")
    parser.add_argument("--ci", action="store_true", help="Run CI test suite")
    parser.add_argument("--report", help="Save detailed report to file")
    
    args = parser.parse_args()
    
    # Se nenhuma opção específica, executar testes rápidos
    if not any([
        args.all, args.unit, args.integration, args.langchain, args.crewai,
        args.examples, args.performance, args.coverage, args.lint, args.security,
        args.fast, args.ci
    ]):
        args.fast = True
    
    runner = TestRunner(verbose=args.verbose)
    
    # Verificar ambiente
    if not runner.check_environment():
        print("❌ Environment check failed!")
        sys.exit(1)
    
    print(f"\n🚀 Starting test execution...")
    start_time = time.time()
    
    overall_success = True
    
    # Executar testes baseado nos argumentos
    if args.fast or args.ci:
        print("\n📋 Running fast test suite...")
        if not runner.run_unit_tests():
            overall_success = False
        if not runner.run_example_tests():
            overall_success = False
        if args.ci and not runner.run_lint_checks():
            overall_success = False
    
    if args.all or args.unit:
        if not runner.run_unit_tests():
            overall_success = False
    
    if args.all or args.integration:
        if not runner.run_integration_tests(with_api=args.with_api):
            overall_success = False
    
    if args.all or args.langchain:
        if not runner.run_langchain_tests():
            overall_success = False
    
    if args.all or args.crewai:
        if not runner.run_crewai_tests():
            overall_success = False
    
    if args.all or args.examples:
        if not runner.run_example_tests():
            overall_success = False
    
    if args.all or args.performance:
        if not runner.run_performance_tests():
            overall_success = False
    
    if args.coverage:
        if not runner.run_coverage_tests():
            overall_success = False
    
    if args.all or args.lint:
        if not runner.run_lint_checks():
            overall_success = False
    
    if args.security:
        if not runner.run_security_checks():
            overall_success = False
    
    # Gerar relatório
    total_duration = time.time() - start_time
    report = runner.generate_report()
    
    print(report)
    print(f"\n⏱️  Total execution time: {total_duration:.2f}s")
    
    # Salvar relatório se solicitado
    if args.report:
        report_path = Path(args.report)
        with open(report_path, "w") as f:
            f.write(report)
            f.write(f"\nTotal execution time: {total_duration:.2f}s\n")
        print(f"📄 Report saved to {report_path}")
    
    # Status final
    if overall_success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 