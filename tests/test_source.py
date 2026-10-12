import ast
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "src" / "server.py"

def test_python_syntax():
    ast.parse(FILE.read_text())

def test_tools_registered():
    tree = ast.parse(FILE.read_text())
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)
             and any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool"
                     for d in n.decorator_list)]
    assert len(names) >= 50
    assert len(names) == len(set(names))
    assert "create_application" not in names
    assert "create_identity_attribute" not in names
