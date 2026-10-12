import ast
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from demo_backend import demo_request


def test_demo_user_list():
    result=demo_request("GET","Users",{"count":2})
    assert result["totalResults"]==3
    assert len(result["Resources"])==2


def test_demo_filter():
    result=demo_request("GET","Users",{"filter":'userName eq "alex.chen"'})
    assert [u["userName"] for u in result["Resources"]]==["alex.chen"]


def test_demo_never_writes():
    assert demo_request("POST","Users",payload={"userName":"test"})["status_code"]==403


def test_registered_tools_count():
    code=Path(__file__).resolve().parents[1]/"src"/"server.py"
    tree=ast.parse(code.read_text())
    tools=[node for node in tree.body if isinstance(node,ast.FunctionDef) and any(isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=="tool" for d in node.decorator_list)]
    assert len(tools)==54
