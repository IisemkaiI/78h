import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <main className="page page--centered">
      <p className="eyebrow">404</p>
      <h1 className="page__title">Страница не найдена</h1>
      <p className="muted">Возможно, ссылка устарела или содержит ошибку.</p>
      <Link className="button button--primary" to="/">
        На главную
      </Link>
    </main>
  );
}
