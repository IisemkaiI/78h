/** Small badge for the three lesson states. */

import type { LessonState } from '../../types/api';
import { lessonStateLabel } from '../../utils/labels';

export function LessonStateBadge({ state }: { state: LessonState }) {
  return (
    <span className={`badge badge--lesson-${state.replace('_', '-')}`}>
      {lessonStateLabel(state)}
    </span>
  );
}
