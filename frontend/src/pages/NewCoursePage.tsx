import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import {
  CourseFields,
  EMPTY_COURSE_FORM,
  type CourseFormValues,
} from '../components/course/CourseFields';
import { useAuth } from '../auth/AuthContext';
import { createCourse } from '../services/courseService';
import { listCategories } from '../services/catalogService';
import type { Category } from '../types/api';
import { describeCourseError } from '../utils/courseErrors';
import '../styles/editor.css';

export function NewCoursePage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [values, setValues] = useState<CourseFormValues>(EMPTY_COURSE_FORM);
  const [categories, setCategories] = useState<Category[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listCategories(controller.signal)
      .then(setCategories)
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (token === null) {
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const course = await createCourse(token, {
        title: values.title.trim(),
        short_description: values.short_description.trim(),
        description: values.description.trim(),
        cover_image_url: values.cover_image_url.trim() || null,
        level: values.level,
        language: values.language.trim().toLowerCase(),
        category_id: values.category_id,
      });
      navigate(`/author/courses/${course.id}`, { replace: true });
    } catch (caught) {
      setError(describeCourseError(caught));
      setSaving(false);
    }
  };

  return (
    <main className="page">
      <header className="page__heading">
        <Link className="course-page__back" to="/author">
          ← Мои курсы
        </Link>
        <p className="eyebrow">Новый курс</p>
        <h1 className="page__title">Создание черновика</h1>
        <p className="muted">
          Заполните основную информацию. Модули и уроки добавляются на следующем шаге, а
          публикация станет доступна после проверки содержания.
        </p>
      </header>

      <form className="card stack" onSubmit={handleSubmit} noValidate>
        {error !== null && (
          <p className="alert alert--error" role="alert">
            {error}
          </p>
        )}

        <CourseFields
          values={values}
          categories={categories}
          disabled={saving}
          onChange={setValues}
          idPrefix="new-course"
        />

        <div className="editor-actions">
          <button type="submit" className="button button--primary" disabled={saving}>
            {saving ? 'Создание…' : 'Создать черновик'}
          </button>
          <Link className="button button--ghost" to="/author">
            Отмена
          </Link>
        </div>
      </form>
    </main>
  );
}
