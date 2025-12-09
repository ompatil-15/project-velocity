# New architecture nodes
# These use the BaseNode class with clear contracts

from app.core.nodes.input_parser import InputParserNode
from app.core.nodes.doc_intelligence import DocIntelligenceNode
from app.core.nodes.bank_verifier import BankVerifierNode
from app.core.nodes.web_compliance import WebComplianceNode
from app.core.nodes.consultant import ConsultantNode
from app.core.nodes.finalizer import FinalizerNode

__all__ = [
    "InputParserNode",
    "DocIntelligenceNode",
    "BankVerifierNode",
    "WebComplianceNode",
    "ConsultantNode",
    "FinalizerNode",
]

