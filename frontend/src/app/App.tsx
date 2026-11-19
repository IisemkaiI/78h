import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { AuthProvider } from '../auth/AuthContext';
import { ProtectedRoute } from '../auth/ProtectedRoute';
import { RequirePermission } from '../auth/RequirePermission';
import { AppLayout } from './AppLayout';
import { AuthorCoursesPage } from '../pages/AuthorCoursesPage';
import { CatalogPage } from '../pages/CatalogPage';
import { CourseDetailPage } from '../pages/CourseDetailPage';
import { CourseEditorPage } from '../pages/CourseEditorPage';
import { HomePage } from '../pages/HomePage';
import { LoginPage } from '../pages/LoginPage';
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
