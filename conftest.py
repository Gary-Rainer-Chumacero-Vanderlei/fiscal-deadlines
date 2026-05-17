# =============================================================================
# conftest.py — Fiscal Deadlines
# Configuração global do pytest.
#
# Resolve o sys.path para que pytest e Streamlit encontrem src/ e config/.
# Carregado automaticamente pelo pytest antes de qualquer teste.
#
# Nota:
#   O Streamlit adiciona apenas dashboard/ ao path — sem este arquivo,
#   imports de src/ e config/ falhariam em produção.
# =============================================================================

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
