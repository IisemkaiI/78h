import assert from 'node:assert/strict';
import test from 'node:test';

import {
  canLeaveOrganization,
  canManageMember,
  canRevokeInvitation,
  editableMemberRoles,
  invitationRoles,
} from '../src/organizations/policy.ts';

const owner = { id: 'owner-membership', user_id: 'owner-user', role: 'owner' };
const admin = { id: 'admin-membership', user_id: 'admin-user', role: 'admin' };
const manager = { id: 'manager-membership', user_id: 'manager-user', role: 'manager' };
const employee = { id: 'employee-membership', user_id: 'employee-user', role: 'employee' };

test('Owner can manage scoped members but cannot remove self or last owner', () => {
  assert.equal(canManageMember('owner', employee, 'owner-user', 1), true);
  assert.equal(canManageMember('owner', owner, 'owner-user', 2), false);
  assert.equal(canManageMember('owner', owner, 'another-user', 1), false);
  assert.deepEqual(editableMemberRoles('owner', 'employee', 1), ['owner', 'admin', 'manager', 'employee']);
  assert.deepEqual(editableMemberRoles('owner', 'owner', 1), []);
  assert.deepEqual(invitationRoles('owner'), ['admin', 'manager', 'employee']);
  assert.equal(canLeaveOrganization('owner', 1), false);
  assert.equal(canLeaveOrganization('owner', 2), true);
});

test('Admin can manage employee and manager roles, but not owner or admin', () => {
  assert.equal(canManageMember('admin', employee, 'admin-user', 1), true);
  assert.equal(canManageMember('admin', manager, 'admin-user', 1), true);
  assert.equal(canManageMember('admin', owner, 'admin-user', 2), false);
  assert.equal(canManageMember('admin', admin, 'admin-user', 1), false);
  assert.deepEqual(editableMemberRoles('admin', 'employee', 1), ['employee', 'manager']);
  assert.deepEqual(editableMemberRoles('admin', 'owner', 2), []);
  assert.deepEqual(invitationRoles('admin'), ['manager', 'employee']);
  assert.equal(canRevokeInvitation('admin', 'admin', 'pending'), false);
  assert.equal(canRevokeInvitation('admin', 'manager', 'pending'), true);
});

test('Manager is limited to employees and employee invitations', () => {
  assert.equal(canManageMember('manager', employee, 'manager-user', 1), true);
  assert.equal(canManageMember('manager', manager, 'manager-user', 2), false);
  assert.deepEqual(editableMemberRoles('manager', 'employee', 1), []);
  assert.deepEqual(invitationRoles('manager'), ['employee']);
  assert.equal(canRevokeInvitation('manager', 'employee', 'pending'), true);
  assert.equal(canRevokeInvitation('manager', 'manager', 'pending'), false);
  assert.equal(canManageMember('manager', { ...employee, can_update_role: false, can_remove: false }, 'manager-user', 1), false);
});

test('Employee and platform administrator do not receive scoped management actions', () => {
  assert.equal(canManageMember('employee', employee, 'other-user', 1), false);
  assert.deepEqual(invitationRoles('employee'), []);
  assert.equal(canLeaveOrganization('employee', 0), true);
  assert.equal(canManageMember('platform_admin', employee, 'admin-user', 1), false);
  assert.deepEqual(invitationRoles('platform_admin'), []);
});
