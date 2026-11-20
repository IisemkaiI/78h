import { Link } from 'react-router-dom';

import { ConnectionStatus } from '../components/ConnectionStatus/ConnectionStatus';
import { useAuth } from '../auth/AuthContext';
import { useBackendStatus } from '../hooks/useBackendStatus';

const pathways = [
  {
    number: '01',
    title: 'Найдите свой курс',
    text: 'Практичные программы от авторов, которым есть чем поделиться.',
    href: '/catalog',
    action: 'Открыть каталог',
    mark: '↗',
  },
  {
    number: '02',
    title: 'Учитесь в своём темпе',
    text: 'Уроки, задания и прогресс остаются с вами — возвращайтесь когда удобно.',
    href: '/my-learning',
    action: 'Продолжить обучение',
    mark: '↘',
  },
  {
    number: '03',
    title: 'Создавайте знания',
    text: 'Соберите программу курса и помогите другим сделать следующий шаг.',
    href: '/author',
    action: 'Стать автором',
    mark: '＋',
  },
];

export function HomePage() {
  const { state, refresh } = useBackendStatus();
  const { status } = useAuth();

  return (
    <main className="home-page">
      <section className="home-hero" aria-labelledby="home-title">
        <div className="home-hero__copy">
          <p className="home-hero__eyebrow">
            <span className="home-hero__live" /> Открытое образование · без оплаты
          </p>
          <h1 id="home-title">
            Знания
            <br />
            меняют <em>траекторию.</em>
          </h1>
          <div className="home-hero__bottom">
            <p>
              Курсы, которые помогают двигаться дальше. Учитесь, делитесь опытом и
              создавайте собственные образовательные программы.
            </p>
            <div className="home-hero__actions">
              <Link className="button button--lime" to="/catalog">
                Выбрать курс <span aria-hidden="true">↗</span>
              </Link>
              {status === 'authenticated' ? (
                <Link className="home-hero__text-link" to="/my-learning">
                  Вернуться к обучению →
                </Link>
              ) : (
                <Link className="home-hero__text-link" to="/register">
                  Создать аккаунт →
                </Link>
              )}
            </div>
          </div>
        </div>
        <div className="home-hero__art" aria-hidden="true">
          <div className="home-orbit home-orbit--outer" />
          <div className="home-orbit home-orbit--inner" />
          <div className="home-hero__sun">
            учись
            <br />
            своим
            <br />
            <i>путём</i>
          </div>
          <span className="home-hero__axis home-hero__axis--top">ИДЕИ В ДЕЙСТВИЕ</span>
          <span className="home-hero__axis home-hero__axis--bottom">ЗНАНИЯ БЕЗ ГРАНИЦ</span>
          <span className="home-hero__orbit-label">EP / 2026</span>
        </div>
        <div className="home-hero__index">
          <span>01</span>
          <span>ОБРАЗОВАНИЕ, КОТОРОЕ ДВИЖЕТ</span>
          <span>↘</span>
        </div>
      </section>

      <section className="home-intro" aria-label="О платформе">
        <p className="home-intro__label">НАЧНИТЕ С ТОГО, ЧТО ВАЖНО</p>
        <p className="home-intro__statement">
          Платформа для тех, кто <span>учится всю жизнь</span> — и тех, кто готов учить.
        </p>
        <p className="home-intro__note">Открыто. Бесплатно. В вашем ритме.</p>
      </section>

      <section className="home-pathways" aria-label="Что можно делать на платформе">
        {pathways.map((item) => (
          <article className="pathway" key={item.number}>
            <div className="pathway__top"><span>{item.number} / 03</span><span className="pathway__mark" aria-hidden="true">{item.mark}</span></div>
            <h2>{item.title}</h2>
            <p>{item.text}</p>
            <Link to={item.href}>{item.action}<span aria-hidden="true"> ↗</span></Link>
          </article>
        ))}
      </section>

      <section className="home-availability">
        <div>
          <p className="home-hero__eyebrow">ПЛАТФОРМА В РАБОТЕ</p>
          <h2>Готовы начать?</h2>
          <p>Проверьте доступность платформы и отправляйтесь за новыми знаниями.</p>
        </div>
        <ConnectionStatus {...state} onRefresh={refresh} />
        <Link className="button button--dark" to="/catalog">
          Все курсы <span aria-hidden="true">↗</span>
        </Link>
      </section>
    </main>
  );
}
