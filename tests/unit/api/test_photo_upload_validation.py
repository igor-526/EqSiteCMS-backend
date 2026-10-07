"""Unit tests for batch upload DTO validation (BE-4).

Тесты для валидации PricePhotosUploadDto, HorsePhotosUploadDto, NewsPhotosUploadDto:
- min 1 file
- max 20 files
"""

import pytest
from pydantic import ValidationError

from core.schemas.horses import HorsePhotosUploadDto
from core.schemas.news import NewsPhotosUploadDto
from core.schemas.prices import PricePhotosUploadDto


def test_price_photos_upload_dto_min_files_validation():
    """Тест валидации минимального количества файлов для PricePhotosUploadDto."""
    # Act & Assert - пустой массив файлов
    with pytest.raises(ValidationError) as exc_info:
        PricePhotosUploadDto(files=[])

    # Проверяем что ошибка связана с min_length
    errors = exc_info.value.errors()
    assert any(
        "at least 1" in str(e).lower() or "min_length" in str(e).lower() for e in errors
    )


def test_price_photos_upload_dto_max_files_validation():
    """Тест валидации максимального количества файлов для PricePhotosUploadDto."""
    # Arrange - создаём 21 файл
    files = [b"image" + str(i).encode() for i in range(21)]

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        PricePhotosUploadDto(files=files)

    # Проверяем что ошибка связана с max_length
    errors = exc_info.value.errors()
    assert any(
        "at most 20" in str(e).lower() or "max_length" in str(e).lower() for e in errors
    )


def test_price_photos_upload_dto_valid_single_file():
    """Тест валидации: 1 файл (минимум) валиден."""
    # Act
    dto = PricePhotosUploadDto(files=[b"image1"])

    # Assert
    assert len(dto.files) == 1
    assert dto.names is None
    assert dto.descriptions is None


def test_price_photos_upload_dto_valid_max_files():
    """Тест валидации: 20 файлов (максимум) валидны."""
    # Arrange
    files = [b"image" + str(i).encode() for i in range(20)]

    # Act
    dto = PricePhotosUploadDto(files=files)

    # Assert
    assert len(dto.files) == 20


def test_price_photos_upload_dto_with_metadata():
    """Тест валидации с опциональными метаданными."""
    # Arrange
    files = [b"image1", b"image2"]
    names = ["Photo 1", "Photo 2"]
    descriptions = ["Desc 1", "Desc 2"]

    # Act
    dto = PricePhotosUploadDto(
        files=files,
        names=names,
        descriptions=descriptions,
    )

    # Assert
    assert len(dto.files) == 2
    assert dto.names == names
    assert dto.descriptions == descriptions


def test_horse_photos_upload_dto_min_files_validation():
    """Тест валидации минимального количества файлов для HorsePhotosUploadDto."""
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        HorsePhotosUploadDto(files=[])

    errors = exc_info.value.errors()
    assert any(
        "at least 1" in str(e).lower() or "min_length" in str(e).lower() for e in errors
    )


def test_horse_photos_upload_dto_max_files_validation():
    """Тест валидации максимального количества файлов для HorsePhotosUploadDto."""
    # Arrange
    files = [b"image" + str(i).encode() for i in range(21)]

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        HorsePhotosUploadDto(files=files)

    errors = exc_info.value.errors()
    assert any(
        "at most 20" in str(e).lower() or "max_length" in str(e).lower() for e in errors
    )


def test_horse_photos_upload_dto_valid_range():
    """Тест валидации: 1-20 файлов валидны для HorsePhotosUploadDto."""
    # 1 файл
    dto1 = HorsePhotosUploadDto(files=[b"image1"])
    assert len(dto1.files) == 1

    # 20 файлов
    files20 = [b"image" + str(i).encode() for i in range(20)]
    dto20 = HorsePhotosUploadDto(files=files20)
    assert len(dto20.files) == 20


def test_news_photos_upload_dto_min_files_validation():
    """Тест валидации минимального количества файлов для NewsPhotosUploadDto."""
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        NewsPhotosUploadDto(files=[])

    errors = exc_info.value.errors()
    assert any(
        "at least 1" in str(e).lower() or "min_length" in str(e).lower() for e in errors
    )


def test_news_photos_upload_dto_max_files_validation():
    """Тест валидации максимального количества файлов для NewsPhotosUploadDto."""
    # Arrange
    files = [b"image" + str(i).encode() for i in range(21)]

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        NewsPhotosUploadDto(files=files)

    errors = exc_info.value.errors()
    assert any(
        "at most 20" in str(e).lower() or "max_length" in str(e).lower() for e in errors
    )


def test_news_photos_upload_dto_valid_range():
    """Тест валидации: 1-20 файлов валидны для NewsPhotosUploadDto."""
    # 1 файл
    dto1 = NewsPhotosUploadDto(files=[b"image1"])
    assert len(dto1.files) == 1

    # 5 файлов
    files5 = [b"image" + str(i).encode() for i in range(5)]
    dto5 = NewsPhotosUploadDto(files=files5)
    assert len(dto5.files) == 5

    # 20 файлов
    files20 = [b"image" + str(i).encode() for i in range(20)]
    dto20 = NewsPhotosUploadDto(files=files20)
    assert len(dto20.files) == 20
