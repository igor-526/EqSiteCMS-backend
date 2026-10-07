"""Unit tests for NewsService.upload_and_attach_photos (BE-4)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from core.entities.equestrian import EquestrianContext
from core.entities.news import News
from core.exceptions.base import ClientError
from core.schemas.news import NewsPhotosUploadDto
from core.schemas.photos import (
    PhotoBatchUploadResponseDto,
    PhotoOutShortDto,
)
from core.services.news import NewsService
from tests.unit.conftest import (
    TEST_ADMIN_USER,
    TEST_EQUESTRIAN_CONTEXT,
    TEST_EQUESTRIAN_ID,
)


class FakeNewsRepository:
    """Fake news repository для изоляции unit tests."""

    def __init__(self) -> None:
        self.news_items: dict[UUID, News] = {}
        self.photo_relations: dict[UUID, list[MagicMock]] = {}

    async def get_by_id(self, news_id: UUID, *, equestrian_id: UUID) -> News | None:
        """Получить news по id."""
        news = self.news_items.get(news_id)
        if news and news.equestrian_id == equestrian_id:
            return news
        return None

    async def get_news_photos(
        self, news_id: UUID, *, equestrian_id: UUID
    ) -> list[MagicMock]:
        """Получить связи news-photo."""
        return self.photo_relations.get(news_id, [])

    async def set_news_photos(
        self,
        news_id: UUID,
        *,
        photo_ids: list[UUID],
        main_photo_id: UUID | None = None,
        equestrian_id: UUID,
    ) -> None:
        """Установить список фото для news."""
        self.photo_relations[news_id] = []
        for photo_id in photo_ids:
            relation = MagicMock()
            relation.photo_id = photo_id
            relation.is_main = photo_id == main_photo_id
            self.photo_relations[news_id].append(relation)


@pytest.fixture
def fake_news_repository() -> FakeNewsRepository:
    """Создать fake news repository."""
    return FakeNewsRepository()


@pytest.fixture
def mock_photo_service() -> AsyncMock:
    """Создать mock PhotoService."""
    from datetime import datetime, timezone

    from core.entities.photos import Photo

    service = AsyncMock()

    # Default mock для create: возвращает Photo entity с path
    async def create_photo(data, upload, *, equestrian_context: EquestrianContext):
        photo_id = uuid4()
        return Photo(
            id=photo_id,
            name=data.name or upload.filename,
            description=data.description,
            path=f"photos/{photo_id}.jpg",
            equestrian_id=equestrian_context.id,
            created_at=datetime.now(timezone.utc),
        )

    service.create.side_effect = create_photo
    return service


@pytest.fixture
def news_service(
    fake_news_repository: FakeNewsRepository,
    mock_photo_service: AsyncMock,
) -> NewsService:
    """Создать NewsService с fake dependencies."""
    # Mock photo_url_builder to return proper URLs
    photo_url_builder = MagicMock()
    photo_url_builder.build.side_effect = lambda path: f"https://example.com/{path}"

    service = NewsService(
        news_repository=fake_news_repository,
        photo_repository=MagicMock(),
        photo_url_builder=photo_url_builder,
        photo_service=mock_photo_service,
    )
    return service


@pytest.fixture
def test_news(fake_news_repository: FakeNewsRepository) -> News:
    """Создать тестовую новость."""
    from datetime import datetime, timezone

    news = News(
        id=uuid4(),
        name="Test News",
        slug="test-news",
        content="<p>Test content</p>",
        published_at=datetime.now(timezone.utc),
        equestrian_id=TEST_EQUESTRIAN_ID,
    )
    fake_news_repository.news_items[news.id] = news
    return news


@pytest.mark.asyncio
async def test_upload_and_attach_photos_success(
    news_service: NewsService,
    test_news: News,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест успешной загрузки 1 файла к новости."""
    # Arrange
    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = NewsPhotosUploadDto(files=files)

    # Act
    result = await news_service.upload_and_attach_photos(
        test_news.id,
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        user=TEST_ADMIN_USER,
    )

    # Assert
    assert isinstance(result, PhotoBatchUploadResponseDto)
    assert len(result.photos) == 1
    assert result.errors is None or len(result.errors) == 0

    # Проверяем что PhotoService.create вызван 1 раз
    assert mock_photo_service.create.call_count == 1

    # Проверяем что фото успешно создано
    assert isinstance(result.photos[0], PhotoOutShortDto)
    assert result.photos[0].url.startswith("https://")


@pytest.mark.asyncio
async def test_upload_and_attach_photos_multiple_files(
    news_service: NewsService,
    test_news: News,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест загрузки нескольких файлов к новости."""
    # Arrange
    files = [b"image1", b"image2", b"image3"]
    filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
    dto = NewsPhotosUploadDto(files=files)

    # Act
    result = await news_service.upload_and_attach_photos(
        test_news.id,
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        user=TEST_ADMIN_USER,
    )

    # Assert
    assert len(result.photos) == 3
    assert mock_photo_service.create.call_count == 3


@pytest.mark.asyncio
async def test_upload_and_attach_photos_partial_success(
    news_service: NewsService,
    test_news: News,
) -> None:
    """Тест partial success для новости."""
    from datetime import datetime, timezone

    from core.entities.photos import Photo

    # Arrange
    files = [b"image1", b"image2"]
    filenames = ["photo1.jpg", "photo2.jpg"]
    dto = NewsPhotosUploadDto(files=files)

    # Mock PhotoService.create: второй файл вызывает ошибку
    call_count = 0

    async def create_with_error(data, upload, *, equestrian_context):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ClientError("File too large")

        photo_id = uuid4()
        return Photo(
            id=photo_id,
            name=data.name or upload.filename,
            description=data.description,
            path=f"photos/{photo_id}.jpg",
            equestrian_id=equestrian_context.id,
            created_at=datetime.now(timezone.utc),
        )

    news_service.photo_service.create.side_effect = create_with_error

    # Act
    result = await news_service.upload_and_attach_photos(
        test_news.id,
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        user=TEST_ADMIN_USER,
    )

    # Assert
    assert len(result.photos) == 1  # Только 1 успешный
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].index == 1  # Второй файл (index 1)
    assert "File too large" in result.errors[0].message


@pytest.mark.asyncio
async def test_upload_and_attach_photos_news_not_found(
    news_service: NewsService,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест ошибки: несуществующая новость (404)."""
    # Arrange
    non_existent_id = uuid4()
    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = NewsPhotosUploadDto(files=files)

    # Act & Assert
    with pytest.raises(ClientError, match="Новость не найдена"):
        await news_service.upload_and_attach_photos(
            non_existent_id,
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            user=TEST_ADMIN_USER,
        )

    # Проверяем что PhotoService.create не вызывался
    mock_photo_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_and_attach_photos_without_admin_permission(
    news_service: NewsService,
    test_news: News,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест попытки загрузить без admin прав (403)."""
    # Arrange
    from datetime import datetime, timezone

    from core.schemas.users import UserOutDto

    non_admin_user = UserOutDto(
        id=uuid4(),
        equestrian_id=TEST_EQUESTRIAN_ID,
        username="non-admin",
        created_at=datetime.now(timezone.utc),
        scopes=[],  # Нет admin scope
    )

    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = NewsPhotosUploadDto(files=files)

    # Act & Assert
    from core.exceptions.auth import ForbiddenError

    with pytest.raises(ForbiddenError, match="Недостаточно прав"):
        await news_service.upload_and_attach_photos(
            test_news.id,
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            user=non_admin_user,
        )

    # Проверяем что PhotoService.create не вызывался
    mock_photo_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_and_attach_photos_wrong_tenant(
    news_service: NewsService,
    fake_news_repository: FakeNewsRepository,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест попытки загрузить к новости другого tenant (403)."""
    # Arrange
    from datetime import datetime, timezone

    other_tenant_id = uuid4()
    other_news = News(
        id=uuid4(),
        name="Other News",
        slug="other-news",
        content="<p>Other content</p>",
        published_at=datetime.now(timezone.utc),
        equestrian_id=other_tenant_id,
    )
    fake_news_repository.news_items[other_news.id] = other_news

    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = NewsPhotosUploadDto(files=files)

    # Act & Assert - попытка доступа с другим equestrian_context
    with pytest.raises(ClientError, match="Новость не найдена"):
        await news_service.upload_and_attach_photos(
            other_news.id,
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            user=TEST_ADMIN_USER,
        )

    # Проверяем что PhotoService.create не вызывался
    mock_photo_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_and_attach_photos_with_metadata(
    news_service: NewsService,
    test_news: News,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест загрузки с метаданными для новости."""
    # Arrange
    files = [b"image1", b"image2"]
    filenames = ["photo1.jpg", "photo2.jpg"]
    dto = NewsPhotosUploadDto(
        files=files,
        names=["News Photo 1", "News Photo 2"],
        descriptions=["Main event", "Details"],
    )

    # Act
    result = await news_service.upload_and_attach_photos(
        test_news.id,
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        user=TEST_ADMIN_USER,
    )

    # Assert
    assert len(result.photos) == 2

    # Проверяем что PhotoService.create вызван с правильными метаданными
    calls = mock_photo_service.create.call_args_list
    assert len(calls) == 2
    assert calls[0][0][0].name == "News Photo 1"
    assert calls[0][0][0].description == "Main event"


@pytest.mark.asyncio
async def test_upload_and_attach_photos_photo_service_not_initialized(
    fake_news_repository: FakeNewsRepository,
    test_news: News,
) -> None:
    """Тест ошибки: PhotoService не инициализирован."""
    # Arrange
    service = NewsService(
        news_repository=fake_news_repository,
        photo_repository=MagicMock(),
        photo_url_builder=MagicMock(),
        photo_service=None,
    )

    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = NewsPhotosUploadDto(files=files)

    # Act & Assert
    with pytest.raises(ClientError, match="PhotoService не инициализирован"):
        await service.upload_and_attach_photos(
            test_news.id,
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            user=TEST_ADMIN_USER,
        )


@pytest.mark.asyncio
async def test_upload_and_attach_photos_full_failure(
    news_service: NewsService,
    test_news: News,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест полного провала: все файлы с ошибками."""
    # Arrange
    files = [b"image1", b"image2", b"image3"]
    filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
    dto = NewsPhotosUploadDto(files=files)

    # Mock PhotoService.create: все файлы вызывают ошибку
    mock_photo_service.create.side_effect = ClientError("Invalid image format")

    # Act
    result = await news_service.upload_and_attach_photos(
        test_news.id,
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        user=TEST_ADMIN_USER,
    )

    # Assert
    assert isinstance(result, PhotoBatchUploadResponseDto)
    assert len(result.photos) == 0  # Нет успешных
    assert result.errors is not None
    assert len(result.errors) == 3  # Все файлы с ошибками
    assert all("Invalid image format" in e.message for e in result.errors)
