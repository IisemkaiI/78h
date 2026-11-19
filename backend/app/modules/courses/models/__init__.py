"""Importing this package registers every course table on ``Base.metadata``."""

from app.modules.courses.models.category import Category
from app.modules.courses.models.course import Course
from app.modules.courses.models.lesson import Lesson
from app.modules.courses.models.module import CourseModule

__all__ = ["Category", "Course", "CourseModule", "Lesson"]
