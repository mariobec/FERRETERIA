"""Formato teléfono ticket."""
import pytest

from services.ticket_impresion_service import telefono_ticket_display


@pytest.mark.parametrize(
    'raw, expected',
    [
        ('5695331233', '+5695331233'),
        ('+5695331233', '+5695331233'),
        ('953312233', '+56953312233'),
    ],
)
def test_telefono_ticket_display(raw, expected):
    assert telefono_ticket_display(raw) == expected
