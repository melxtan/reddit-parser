from pathlib import Path
from typing import Dict

from jinja2 import Template, meta


def load_prompt(prompt_name: str, variables: Dict[str, str] | None = None) -> str:
    """
    Load and optionally render a prompt template.

    Args:
        prompt_name: Name of the prompt file without .xml extension
        variables: Optional dictionary of variables to substitute
    """
    prompt_dir = Path(__file__).parent / "prompts"
    prompt_path = prompt_dir / f"{prompt_name}.xml"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        content = f.read()

    if variables:
        template = Template(content)
        return template.render(**variables)

    return content


def get_template_variables(content: str) -> set[str]:
    """Extract Jinja2 template variables from content string."""
    env = Template(content).environment
    ast = env.parse(content)
    return meta.find_undeclared_variables(ast)


if __name__ == "__main__":
    prompt_dir = Path(__file__).parent / "prompts"
    prompt_files = prompt_dir.glob("*.xml")

    # Example variable value to substitute
    example_vars = {"search_query": "sneakers"}

    for prompt_file in prompt_files:
        print(f"\nAnalyzing {prompt_file.name}:")

        # Get template variables
        with open(prompt_file, "r", encoding="utf-8") as f:
            content = f.read()
            variables = get_template_variables(content)
            if variables:
                print("Template variables found:")
                for var in sorted(variables):
                    print(f"  - {var}")
            else:
                print("No template variables found")

        # Render template with example values
        rendered = load_prompt(prompt_file.stem, example_vars)

        # Parse XML and print structure
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(rendered)
        except ET.ParseError as e:
            print(f"\nXML Parsing Error: {e}")
            print("First 200 characters of rendered content:")
            print(rendered[:200])
            continue

        def print_structure(element, level=0):
            print("  " * level + f"<{element.tag}>")
            for child in element:
                print_structure(child, level + 1)

        print("\nXML Structure:")
        print_structure(root)
