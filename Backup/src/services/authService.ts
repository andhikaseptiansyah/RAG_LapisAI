import jwt from 'jsonwebtoken';
import type { SignOptions } from 'jsonwebtoken';

import { env } from '../config/env.js';
import { query } from '../config/database.js';

export type AuthRole = 'user' | 'staff' | 'admin' | 'superadmin' | 'owner';

export interface AuthUser {
  id: string;
  username: string;
  name: string;
  email?: string | null;
  role: AuthRole;
}

interface LoginInput {
  username: string;
  password: string;
}

interface LoginResult {
  token: string;
  user: AuthUser;
}

interface DbAuthUserRow {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  role: string;
}

const allowedRoles = new Set<AuthRole>([
  'user',
  'staff',
  'admin',
  'superadmin',
  'owner',
]);

const normalizeRole = (role: string): AuthRole => {
  return allowedRoles.has(role as AuthRole)
    ? (role as AuthRole)
    : 'user';
};

const toPublicUser = (row: DbAuthUserRow): AuthUser => ({
  id: row.id,
  username: row.username,
  name: row.display_name,
  email: row.email,
  role: normalizeRole(row.role),
});

const getJwtSecret = (): string => {
  if (!env.JWT_SECRET) {
    throw new Error('JWT_SECRET belum diisi di file .env.');
  }

  return env.JWT_SECRET;
};

export const createTokenForUser = (user: AuthUser): string => {
  const options: SignOptions = {
    expiresIn: env.JWT_EXPIRES_IN as SignOptions['expiresIn'],
  };

  return jwt.sign(
    {
      id: user.id,
      username: user.username,
      name: user.name,
      email: user.email,
      role: user.role,
    },
    getJwtSecret(),
    {
      ...options,
      subject: user.id,
    }
  );
};

export const loginUser = async (input: LoginInput): Promise<LoginResult> => {
  const username = input.username.trim();
  const password = input.password;

  if (!username || !password) {
    throw new Error('Username dan password wajib diisi.');
  }

  const result = await query<DbAuthUserRow>(
    `
      SELECT
        id::text AS id,
        username,
        display_name,
        email,
        role::text AS role
      FROM public.app_users
      WHERE lower(username) = lower($1)
        AND password_hash IS NOT NULL
        AND password_hash = crypt($2, password_hash)
        AND is_active = true
      ORDER BY
        CASE role::text
          WHEN 'admin' THEN 1
          WHEN 'superadmin' THEN 1
          WHEN 'owner' THEN 1
          ELSE 2
        END,
        created_at ASC
      LIMIT 1
    `,
    [username, password]
  );

  const userRow = result.rows[0];

  if (!userRow) {
    throw new Error('Username atau password salah.');
  }

  const user = toPublicUser(userRow);

  return {
    token: createTokenForUser(user),
    user,
  };
};
