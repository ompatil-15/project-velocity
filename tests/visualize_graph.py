"""
Visualize the LangGraph workflow using LangGraph's internal methods.
Run: python tests/visualize_graph.py

Outputs: graph.png

For Jupyter notebook:
    from tests.visualize_graph import get_graph_image
    get_graph_image()  # Returns IPython.display.Image
"""
import sys
sys.path.insert(0, ".")

from app.graph import build_graph


def get_graph_image():
    """Returns graph as IPython Image (for notebooks)."""
    from IPython.display import Image
    
    workflow = build_graph()
    graph = workflow.compile()
    
    # Try draw_png (requires pygraphviz), fallback to draw_mermaid_png
    try:
        png_data = graph.get_graph().draw_png()
    except ImportError:
        png_data = graph.get_graph().draw_mermaid_png()
    
    return Image(png_data)


def main():
    print("Building graph...")
    workflow = build_graph()
    
    # Compile without checkpointer for visualization
    graph = workflow.compile()
    
    # Try draw_png (requires pygraphviz), fallback to draw_mermaid_png
    try:
        print("Generating graph using draw_png()...")
        png_data = graph.get_graph().draw_png()
    except ImportError:
        print("pygraphviz not installed, using draw_mermaid_png()...")
        png_data = graph.get_graph().draw_mermaid_png()
    
    with open("graph.png", "wb") as f:
        f.write(png_data)
    
    print("Saved to graph.png")


if __name__ == "__main__":
    main()
