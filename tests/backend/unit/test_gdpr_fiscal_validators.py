import pytest
from app.utils.fiscal_validators import (
    validate_nif,
    validate_nie,
    validate_cif,
    is_valid_spanish_id
)

def test_valid_nif():
    # 12345678Z -> 12345678 % 23 = 14 -> Z
    assert validate_nif("12345678Z") is True
    assert validate_nif("12345678-Z") is True
    assert validate_nif("12.345.678-Z") is True

def test_invalid_nif():
    # Letra errónea
    assert validate_nif("12345678A") is False
    # Longitud incorrecta
    assert validate_nif("1234567Z") is False
    assert validate_nif("123456789Z") is False

def test_valid_nie():
    # X1234567L -> X0 -> 01234567 % 23 = 10 -> L
    assert validate_nie("X1234567L") is True
    # Y1234567X -> Y1 -> 11234567 % 23 = 9 -> X
    assert validate_nie("Y1234567X") is True
    # Z1234567R -> Z2 -> 21234567 % 23 = 1 -> R
    assert validate_nie("Z1234567R") is True

def test_invalid_nie():
    assert validate_nie("X1234567A") is False
    assert validate_nie("W1234567L") is False

def test_valid_cif():
    # B12345674 (Sociedad limitada con control numérico)
    assert validate_cif("B12345674") is True
    assert validate_cif("B-12.345.674") is True

def test_invalid_cif():
    assert validate_cif("B12345679") is False
    assert validate_cif("Z12345674") is False

def test_is_valid_spanish_id_dispatcher():
    assert is_valid_spanish_id("12345678Z") == ("NIF", True)
    assert is_valid_spanish_id("X1234567L") == ("NIE", True)
    assert is_valid_spanish_id("B12345674") == ("CIF", True)
    assert is_valid_spanish_id("99999999X") == (None, False)
