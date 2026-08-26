from .c import MAP_REPO_TO_PARSER_C
from .go import MAP_REPO_TO_PARSER_GO
from .java import MAP_REPO_TO_PARSER_JAVA
from .javascript import MAP_REPO_TO_PARSER_JS
from .php import MAP_REPO_TO_PARSER_PHP
from .python import MAP_REPO_TO_PARSER_PY
from .ruby import MAP_REPO_TO_PARSER_RUBY
from .rust import MAP_REPO_TO_PARSER_RUST

MAP_REPO_TO_PARSER = {
    **MAP_REPO_TO_PARSER_C,
    **MAP_REPO_TO_PARSER_GO,
    **MAP_REPO_TO_PARSER_JAVA,
    **MAP_REPO_TO_PARSER_JS,
    **MAP_REPO_TO_PARSER_PHP,
    **MAP_REPO_TO_PARSER_PY,
    **MAP_REPO_TO_PARSER_RUST,
    **MAP_REPO_TO_PARSER_RUBY,
}


__all__ = [
    "MAP_REPO_TO_PARSER",
]
