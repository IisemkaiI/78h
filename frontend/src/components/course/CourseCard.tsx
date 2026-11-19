import { Link } from 'react-router-dom';

import type { CatalogCourse } from '../../types/api';
import { courseLevelLabel, formatDuration } from '../../utils/labels';

function coverLetter(title: string): string {
  return title.trim().charAt(0).toUpperCase() || 'К';
}

export function CourseCard({ course }: { course: CatalogCourse }) {
  return (
    <article className="course-card">
      <Link className="course-card__cover" to={`/catalog/${course.slug}`} tabIndex={-1} aria-hidden="true">
        {course.cover_image_url ? (
          <img src={course.cover_image_url} alt="" loading="lazy" />
        ) : (
          <span className="course-card__cover-letter">{coverLetter(course.title)}</span>
        )}
      </Link>

      <div className="course-card__body">
        <div className="badge-row">
          <span className="badge">{course.category.name}</span>
          <span className="badge badge--level">{courseLevelLabel(course.level)}</span>
        </div>

        <h2 className="course-card__title">
          <Link to={`/catalog/${course.slug}`}>{course.title}</Link>
        </h2>
        <p className="course-card__description">{course.short_description}</p>

        <dl className="course-card__meta">
          <div>
            <dt>Модули</dt>
            <dd>{course.modules_count}</dd>
          </div>
          <div>
            <dt>Уроки</dt>
            <dd>{course.lessons_count}</dd>
          </div>
          <div>
            <dt>Длительность</dt>
            <dd>{formatDuration(course.total_duration_minutes)}</dd>
          </div>
        </dl>

        <p className="course-card__author">Автор: {course.author.display_name}</p>
      </div>
    </article>
  );
}
