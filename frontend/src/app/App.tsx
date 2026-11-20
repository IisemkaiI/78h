import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { AuthProvider } from '../auth/AuthContext';
import { ProtectedRoute } from '../auth/ProtectedRoute';
import { RequirePermission } from '../auth/RequirePermission';
import { AppLayout } from './AppLayout';
import { AuthorCoursePreviewPage } from '../pages/AuthorCoursePreviewPage';
import { AuthorAssessmentsPage } from '../pages/AuthorAssessmentsPage';
import { AssessmentReviewsPage } from '../pages/AssessmentReviewsPage';
import { AuthorCoursesPage } from '../pages/AuthorCoursesPage';
import { CatalogPage } from '../pages/CatalogPage';
import { CourseDetailPage } from '../pages/CourseDetailPage';
import { CourseEditorPage } from '../pages/CourseEditorPage';
import { HomePage } from '../pages/HomePage';
import { LearnCoursePage } from '../pages/LearnCoursePage';
import { LoginPage } from '../pages/LoginPage';
import { MyLearningPage } from '../pages/MyLearningPage';
import { NewCoursePage } from '../pages/NewCoursePage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { ProfilePage } from '../pages/ProfilePage';
import { RegisterPage } from '../pages/RegisterPage';
import './App.css';

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/catalog" element={<CatalogPage />} />
            <Route path="/catalog/:slug" element={<CourseDetailPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/my-learning"
              element={
                <RequirePermission permission="enrollments:read_own">
                  <MyLearningPage />
                </RequirePermission>
              }
            />
            <Route
              path="/learn/:slug"
              element={
                <RequirePermission permission="enrollments:read_own">
                  <LearnCoursePage />
                </RequirePermission>
              }
            />
            <Route
              path="/learn/:slug/lessons/:lessonId"
              element={
                <RequirePermission permission="enrollments:read_own">
                  <LearnCoursePage />
                </RequirePermission>
              }
            />
            <Route
              path="/author/courses/:courseId/assessments"
              element={
                <RequirePermission permission="assessments:manage_own">
                  <AuthorAssessmentsPage />
                </RequirePermission>
              }
            />
            <Route
              path="/teaching/reviews"
              element={
                <RequirePermission permission={["assessments:review", "assessments:manage_own", "assessments:manage_all"]}>
                  <AssessmentReviewsPage />
                </RequirePermission>
              }
            />
            <Route
              path="/author/courses/:courseId/preview"
              element={
                <RequirePermission permission="courses:create">
                  <AuthorCoursePreviewPage />
                </RequirePermission>
              }
            />
            <Route
              path="/author"
              element={
                <RequirePermission permission="courses:create">
                  <AuthorCoursesPage />
                </RequirePermission>
              }
            />
            <Route
              path="/author/courses/new"
              element={
                <RequirePermission permission="courses:create">
                  <NewCoursePage />
                </RequirePermission>
              }
            />
            <Route
              path="/author/courses/:courseId"
              element={
                <RequirePermission permission="courses:create">
                  <CourseEditorPage />
                </RequirePermission>
              }
            />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </AuthProvider>
  );
}
