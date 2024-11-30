from pathlib import Path
from typing import Dict

from jinja2 import Template, meta


# TODO, will use langfuse format or API
class Prompt:
    def __init__(self, prompt_name: str):
        """
        Initialize a Prompt object.

        Args:
            prompt_name: Name of the prompt file without .xml.j2 extension
        """
        self.prompt_name = prompt_name
        self.variables: Dict[str, str] = {}
        self._template_content = self._load_template()
        self.required_vars = get_template_variables(self._template_content)
        self.template = Template(self._template_content)
        self._content: str = ""

        # If no variables required, render immediately
        if not self.required_vars:
            self._content = self.template.render()

    def _load_template(self) -> str:
        prompt_dir = Path(__file__).parent / "prompts"
        prompt_path = prompt_dir / f"{self.prompt_name}.xml.j2"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    @property
    def content(self) -> str:
        """
        Get the rendered content. Raises ValueError if required variables are not set.
        """
        if self.required_vars and not self._content:
            missing_vars = self.required_vars - set(self.variables.keys())
            if missing_vars:
                raise ValueError(
                    f"Cannot access content: missing required variables: {missing_vars}"
                )
            self._content = self.template.render(**self.variables)
        return self._content

    def set_variables(self, variables: Dict[str, str]) -> "Prompt":
        """
        Set or update template variables and render the content.

        Args:
            variables: Dictionary of variables to substitute

        Returns:
            self for method chaining
        """
        self.variables.update(variables)

        # Only render if we have all required variables
        missing_vars = self.required_vars - set(self.variables.keys())
        if not missing_vars:
            self._content = self.template.render(**self.variables)
        else:
            # Clear previous render if we're missing variables
            self._content = ""

        return self


def load_prompt(
    prompt_name: str,
    variables: Dict[str, str] | None = None,
) -> str:
    """
    Load and render a prompt template.

    Args:
        prompt_name: Name of the prompt file without .xml extension
        variables: Optional dictionary of variables to substitute

    Returns:
        Rendered prompt string

    Raises:
        ValueError: If template requires variables that aren't provided
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt = Prompt(prompt_name)
    if variables:
        prompt.set_variables(variables)
    return prompt.content

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
