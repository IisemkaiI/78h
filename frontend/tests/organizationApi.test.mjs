import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { createServer } from 'vite';

let vite;
let api;
let adminApi;
const originalFetch = globalThis.fetch;

before(async () => {
  vite = await createServer({
    configFile: 'vite.config.ts',
    appType: 'custom',
    logLevel: 'silent',
    server: { middlewareMode: true },
  });
  api = await vite.ssrLoadModule('/src/services/organizationService.ts');
  adminApi = await vite.ssrLoadModule('/src/services/adminService.ts');
  globalThis.window = { setTimeout, clearTimeout };
});

after(async () => {
  globalThis.fetch = originalFetch;
  delete globalThis.window;
  await vite?.close();
});

test('invitation creation sends the scoped URL, bearer token and selected role', async () => {
  globalThis.fetch = async (url, init) => {
    assert.match(String(url), /\/api\/v1\/organizations\/org-1\/invitations$/);
    assert.equal(init.method, 'POST');
    assert.equal(init.headers.Authorization, 'Bearer session-token');
    assert.deepEqual(JSON.parse(init.body), { email: 'learner@example.com', role: 'employee' });
    return new Response(JSON.stringify({ id: 'invite-1', token: 'one-time-token' }), {
      status: 201, headers: { 'Content-Type': 'application/json' },
    });
  };
  const result = await api.createInvitation('session-token', 'org-1', 'learner@example.com', 'employee');
  assert.equal(result.token, 'one-time-token');
});

test('bulk assignment serializes selected members and due date without changing API names', async () => {
  globalThis.fetch = async (_url, init) => {
    assert.equal(init.method, 'POST');
    assert.deepEqual(JSON.parse(init.body), {
      course_id: 'course-1', membership_ids: ['member-1', 'member-2'],
      due_at: '2026-11-30T20:59:59.000Z', is_required: true,
    });
    return new Response('[]', { status: 201 });
  };
  const result = await api.createCorporateAssignments(
    'session-token', 'org-1', 'course-1', ['member-1', 'member-2'],
    '2026-11-30T20:59:59.000Z', true,
  );
  assert.deepEqual(result, []);
});

test('backend 403 envelope stays a typed API error for invitation acceptance', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({
    error: { code: 'invitation_email_mismatch', message: 'Invitation email mismatch', details: null },
  }), { status: 403, headers: { 'Content-Type': 'application/json' } });

  await assert.rejects(
    api.acceptOrganizationInvitation('session-token', 'invitation-secret'),
    (error) => error.status === 403 && error.code === 'invitation_email_mismatch',
  );
});

test('empty 204 mutation response resolves successfully', async () => {
  globalThis.fetch = async (_url, init) => {
    assert.equal(init.method, 'POST');
    return new Response(null, { status: 204 });
  };
  assert.equal(await api.leaveOrganization('session-token', 'org-1'), null);
});

test('department assignment is sent to the organization-scoped endpoint', async () => {
  globalThis.fetch = async (url, init) => {
    assert.match(String(url), /organizations\/org-1\/members\/member-1\/department$/);
    assert.equal(init.method, 'PATCH');
    assert.deepEqual(JSON.parse(init.body), { department_id: 'department-1' });
    return new Response(JSON.stringify({ department_id: 'department-1' }), { status: 200 });
  };
  const result = await api.setMemberDepartment('session-token', 'org-1', 'member-1', 'department-1');
  assert.equal(result.department_id, 'department-1');
});

test('admin user action sends only the requested active flag', async () => {
  globalThis.fetch = async (url, init) => {
    assert.match(String(url), /\/api\/v1\/admin\/users\/user-1$/);
    assert.equal(init.method, 'PATCH');
    assert.equal(init.headers.Authorization, 'Bearer admin-token');
    assert.deepEqual(JSON.parse(init.body), { is_active: false });
    return new Response(JSON.stringify({ id: 'user-1', is_active: false }), { status: 200 });
  };
  const result = await adminApi.setAdminUserActive('admin-token', 'user-1', false);
  assert.equal(result.is_active, false);
});
