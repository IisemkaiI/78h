/** Sprint 5 API calls. Correct answer keys are intentionally absent from learner types. */

import { apiRequest } from './apiClient';
import type { LearningAssignment, LearningQuiz } from '../types/api';

const PREFIX = '/api/v1/assessments';

export interface QuizOption { id: string; text: string }
export interface QuizQuestion {
  id?: string;
  question_type: 'single_choice' | 'multiple_choice' | 'true_false' | 'short_text';
  prompt: string;
  options: QuizOption[];
  answer_key: unknown;
  points: number;
  position: number;
  explanation?: string | null;
}
export interface AuthorQuiz extends LearningQuiz {
  course_id: string;
  lesson_id: string | null;
  status: 'draft' | 'published' | 'archived';
  version: number;
  questions: (QuizQuestion & { id: string })[];
}
export interface QuizAttempt {
  id: string;
  quiz_id: string;
  quiz_version: number;
  questions: {
    id: string;
    question_type: QuizQuestion['question_type'];
    prompt: string;
    options: QuizOption[];
    points: number;
    position: number;
  }[];
  expires_at: string | null;
  started_at: string;
}
export interface AttemptResult {
  id: string;
  quiz_id: string;
  quiz_version: number;
  status: string;
  score: number;
  max_score: number;
  percent: number | null;
  passed: boolean | null;
  attempt_number: number;
  completed_at: string | null;
  answers: { question_id: string; answer: unknown; awarded_points: number; is_correct: boolean | null; explanation: string | null }[];
}
export interface AuthorAssignment extends LearningAssignment {
  course_id: string;
  lesson_id: string | null;
  status: 'draft' | 'published' | 'archived';
}
export interface Submission {
  id: string;
  assignment_id: string;
  user_id: string;
  status: 'draft' | 'submitted' | 'under_review' | 'revision_required' | 'graded';
  draft_text: string | null;
  latest_version: number;
  current_score: number | null;
  is_accepted: boolean | null;
  submitted_at: string | null;
  versions: { id: string; version_number: number; response_text: string; submitted_at: string }[];
  reviews: { id: string; reviewer_id: string; decision: string; score: number; comment: string | null; created_at: string }[];
}

export const createQuiz = (token: string, body: unknown) => apiRequest<AuthorQuiz>(`${PREFIX}/quizzes`, { method: 'POST', body, token });
export const listQuizzes = (token: string, courseId: string) => apiRequest<AuthorQuiz[]>(`${PREFIX}/courses/${courseId}/quizzes`, { token });
export const updateQuiz = (token: string, id: string, body: unknown) => apiRequest<AuthorQuiz>(`${PREFIX}/quizzes/${id}`, { method: 'PATCH', body, token });
export const setQuizStatus = (token: string, id: string, status: 'publish' | 'unpublish' | 'archive') => apiRequest<AuthorQuiz>(`${PREFIX}/quizzes/${id}/${status}`, { method: 'POST', token });
export const startQuiz = (token: string, id: string) => apiRequest<QuizAttempt>(`${PREFIX}/quizzes/${id}/attempts`, { method: 'POST', token });
export const saveQuizAnswers = (token: string, attemptId: string, answers: { question_id: string; answer: unknown }[]) => apiRequest<{ saved: number }>(`${PREFIX}/attempts/${attemptId}/answers`, { method: 'PUT', body: answers, token });
export const submitQuiz = (token: string, attemptId: string) => apiRequest<AttemptResult>(`${PREFIX}/attempts/${attemptId}/submit`, { method: 'POST', token });
export const quizHistory = (token: string, quizId: string) => apiRequest<AttemptResult[]>(`${PREFIX}/quizzes/${quizId}/attempts/mine`, { token });

export const createAssignment = (token: string, body: unknown) => apiRequest<AuthorAssignment>(`${PREFIX}/assignments`, { method: 'POST', body, token });
export const listAssignments = (token: string, courseId: string) => apiRequest<AuthorAssignment[]>(`${PREFIX}/courses/${courseId}/assignments`, { token });
export const updateAssignment = (token: string, id: string, body: unknown) => apiRequest<AuthorAssignment>(`${PREFIX}/assignments/${id}`, { method: 'PATCH', body, token });
export const setAssignmentStatus = (token: string, id: string, status: 'publish' | 'unpublish' | 'archive') => apiRequest<AuthorAssignment>(`${PREFIX}/assignments/${id}/${status}`, { method: 'POST', token });
export const getOwnSubmission = (token: string, id: string) => apiRequest<Submission | null>(`${PREFIX}/assignments/${id}/submission/mine`, { token });
export const saveAssignmentDraft = (token: string, id: string, responseText: string) => apiRequest<Submission>(`${PREFIX}/assignments/${id}/submission/draft`, { method: 'PUT', body: { response_text: responseText }, token });
export const submitAssignment = (token: string, id: string) => apiRequest<Submission>(`${PREFIX}/assignments/${id}/submission/submit`, { method: 'POST', token });
export const listSubmissions = (token: string, id: string) => apiRequest<Submission[]>(`${PREFIX}/assignments/${id}/submissions`, { token });
export const startReview = (token: string, id: string) => apiRequest<Submission>(`${PREFIX}/submissions/${id}/start-review`, { method: 'POST', token });
export const reviewSubmission = (token: string, id: string, body: { decision: 'accepted' | 'revision_required'; score: number; comment: string }) => apiRequest<Submission>(`${PREFIX}/submissions/${id}/review`, { method: 'POST', body, token });
export const teachingCourses = (token: string) => apiRequest<{ id: string; title: string; slug: string; assignments: { id: string; title: string; status: string; is_required: boolean }[] }[]>(`${PREFIX}/teaching`, { token });
export const addInstructor = (token: string, courseId: string, instructorId: string) => apiRequest<unknown>(`${PREFIX}/courses/${courseId}/instructors`, { method: 'POST', body: { instructor_id: instructorId }, token });
export const listInstructors = (token: string, courseId: string) => apiRequest<{ instructor_id: string; display_name: string }[]>(`${PREFIX}/courses/${courseId}/instructors`, { token });
export const removeInstructor = (token: string, courseId: string, instructorId: string) => apiRequest<null>(`${PREFIX}/courses/${courseId}/instructors/${instructorId}`, { method: 'DELETE', token });
