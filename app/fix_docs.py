"""
This python script is part of the Kubespray project to create a collection and will fix the documentation

It will use Jinja2 template to generate the README.md file.
I will find the template in the templates folder.
It will also remove docs and do the same with the docs in templates/doc folder
"""

import os
import sys
import shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocsFixer:
    """Handles documentation fixes for Kubespray collection."""

    def __init__(self, base_path="."):
        """Initialize the DocsFixer.
        
        Args:
            base_path: Base path where templates and docs are located
        """
        self.base_path = Path(base_path)
        self.templates_path = Path("/app/templates")
        self.docs_path = self.base_path / "docs"
        self.templates_docs_path = self.templates_path / "docs"

    def setup_jinja_environment(self):
        """Setup Jinja2 environment for template rendering.
        
        Returns:
            Jinja2 Environment object
        """
        try:
            env = Environment(loader=FileSystemLoader(str(self.templates_path)))
            logger.info(f"Jinja2 environment configured with loader path: {self.templates_path}")
            return env
        except Exception as e:
            logger.error(f"Failed to setup Jinja2 environment: {e}")
            raise

    def generate_readme(self, context=None):
        """Generate README.md file from Jinja2 template.
        
        Args:
            context: Dictionary of variables to pass to the template
            
        Returns:
            Path to the generated README.md file
        """
        if context is None:
            context = {}

        try:
            env = self.setup_jinja_environment()
            template = env.get_template("README.md.j2")
            
            readme_content = template.render(context)
            readme_path = self.base_path / "README.md"
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            logger.info(f"Generated README.md at {readme_path}")
            return readme_path
            
        except TemplateNotFound as e:
            logger.error(f"Template not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to generate README.md: {e}")
            raise

    def remove_docs_directory(self):
        """Remove the docs directory.
        
        Returns:
            True if successful, False otherwise
        """
        if self.docs_path.exists():
            try:
                shutil.rmtree(self.docs_path)
                logger.info(f"Removed docs directory: {self.docs_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to remove docs directory: {e}")
                return False
        else:
            logger.warning(f"Docs directory not found: {self.docs_path}")
            return False

    def process_template_docs(self, context=None):
        """Process and deploy docs from templates/docs folder using Jinja2.
        
        Args:
            context: Dictionary of variables to pass to the template
            
        Returns:
            List of deployed files
        """
        if context is None:
            context = {}
        
        deployed_files = []
        
        if not self.templates_docs_path.exists():
            logger.warning(f"Templates docs directory not found: {self.templates_docs_path}")
            return deployed_files

        try:
            # Create docs directory if it doesn't exist
            self.docs_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created/verified docs directory: {self.docs_path}")
            
            # Setup Jinja2 environment for templates/docs
            env = Environment(loader=FileSystemLoader(str(self.templates_docs_path)))
            
            # Process all .j2 template files
            for template_file in self.templates_docs_path.glob("*.j2"):
                try:
                    template_name = template_file.name
                    template = env.get_template(template_name)
                    
                    # Render the template
                    rendered_content = template.render(context)
                    
                    # Generate output filename (remove .j2 extension)
                    output_filename = template_name[:-3] if template_name.endswith('.j2') else template_name
                    output_path = self.docs_path / output_filename
                    
                    # Write the rendered content to the docs directory
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(rendered_content)
                    
                    logger.info(f"Deployed template doc: {template_name} -> {output_path}")
                    deployed_files.append(str(output_path))
                    
                except Exception as e:
                    logger.error(f"Failed to process template {template_file.name}: {e}")
                    raise
            
            logger.info(f"Deployed {len(deployed_files)} template doc files")
            return deployed_files
            
        except Exception as e:
            logger.error(f"Failed to process template docs: {e}")
            raise

    def run(self, context=None):
        """Execute the documentation fixing process.
        
        Args:
            context: Dictionary of variables to pass to the template
        """
        try:
            logger.info("Starting documentation fixing process...")
            
            # Generate README.md from template
            self.generate_readme(context)
            
            # Remove existing docs directory
            self.remove_docs_directory()
            
            # Process and deploy template docs
            self.process_template_docs(context)
            
            logger.info("Documentation fixing process completed successfully")
            
        except Exception as e:
            logger.error(f"Documentation fixing process failed: {e}")
            raise


def main():
    """Main entry point for the script."""
    # Get the collection directory from command-line argument or use default
    if len(sys.argv) > 1:
        base_path = Path(sys.argv[1])
    else:
        base_path = Path(__file__).parent
    
    if not base_path.exists():
        logger.error(f"Specified path does not exist: {base_path}")
        return 1
    
    logger.info(f"Using base path: {base_path}")
    
    # Create DocsFixer instance
    fixer = DocsFixer(base_path=base_path)
    
    # Read prerequisites from requirements.txt
    prerequisites = []
    requirements_file = base_path / "requirements.txt"
    
    if requirements_file.exists():
        try:
            with open(requirements_file, 'r', encoding='utf-8') as f:
                prerequisites = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            logger.info(f"Read {len(prerequisites)} prerequisites from requirements.txt")
        except Exception as e:
            logger.warning(f"Failed to read requirements.txt: {e}")
    else:
        logger.warning(f"requirements.txt not found at {requirements_file}")
    
    # Define context for template rendering
    context = {
        'prerequisites': prerequisites,
        'galaxy_target': os.getenv("GALAXY_TARGET", "kubernetes_sigs_kubespray"),
    }
    
    try:
        # Run the documentation fixing process
        fixer.run(context)
        logger.info("Process completed successfully")
        return 0
    except Exception as e:
        logger.error(f"Process failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
