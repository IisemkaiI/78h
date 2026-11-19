"""Course schemas package."""

from app.modules.courses.schemas.category import CategoryBrief, CategoryRead
from app.modules.courses.schemas.common import ReorderRequest
from app.modules.courses.schemas.course import (
    AuthorRead,
    CatalogCourseDetail,
    CatalogCourseRead,
    CatalogPage,
    CourseCreate,
    CourseDetail,
    CoursePage,
    CourseSummary,
    CourseUpdate,
)
from app.modules.courses.schemas.lesson import (
    LessonCreate,
    LessonPreview,
    LessonRead,
    LessonUpdate,
)
from app.modules.courses.schemas.module import (
    ModuleCreate,
    ModulePreview,
    ModuleRead,
    ModuleUpdate,
)

__all__ = [
    "AuthorRead",
    "CatalogCourseDetail",
    "CatalogCourseRead",
    "CatalogPage",
    "CategoryBrief",
    "CategoryRead",
    "CourseCreate",
    "CourseDetail",
    "CoursePage",
    "CourseSummary",
    "CourseUpdate",
    "LessonCreate",
    "LessonPreview",
    "LessonRead",
    "LessonUpdate",
    "ModuleCreate",
    "ModulePreview",
    "ModuleRead",
    "ModuleUpdate",
    "ReorderRequest",
]
