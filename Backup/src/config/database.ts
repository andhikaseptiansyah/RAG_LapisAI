import {
  Pool,
  PoolClient,
  QueryResult,
  QueryResultRow,
} from 'pg';

import { env } from './env.js';

const sslConfiguration =
  env.DATABASE_SSL
    ? {
        rejectUnauthorized:
          env.DATABASE_SSL_REJECT_UNAUTHORIZED,
      }
    : undefined;

export const pool = new Pool({
  connectionString:
    env.DATABASE_URL,

  ssl: sslConfiguration,

  max:
    env.DATABASE_POOL_MAX,

  idleTimeoutMillis:
    env.DATABASE_IDLE_TIMEOUT_MS,

  connectionTimeoutMillis:
    env.DATABASE_CONNECTION_TIMEOUT_MS,

  application_name:
    'lapisai-backend',
});

/**
 * Menangani error pada client PostgreSQL
 * yang sedang tidak dipakai.
 */
pool.on(
  'error',
  (error: Error) => {
    console.error(
      '[DATABASE] Unexpected pool error:',
      error.message
    );
  }
);

/**
 * Menjalankan query PostgreSQL biasa.
 *
 * Gunakan parameter $1, $2, dan seterusnya
 * untuk mencegah SQL injection.
 */
export const query = async <
  T extends QueryResultRow =
    QueryResultRow
>(
  text: string,
  params: unknown[] = []
): Promise<QueryResult<T>> => {
  return pool.query<T>(
    text,
    params
  );
};

/**
 * Menguji koneksi database.
 *
 * Panggil fungsi ini ketika server mulai.
 */
export const testDatabaseConnection =
  async (): Promise<void> => {
    const result = await pool.query<{
      current_time: Date;
      database_name: string;
    }>(
      `
        SELECT
          NOW() AS current_time,
          CURRENT_DATABASE() AS database_name
      `
    );

    const connectionInfo =
      result.rows[0];

    console.log(
      `[DATABASE] Connected to "${connectionInfo.database_name}" at ${connectionInfo.current_time.toISOString()}`
    );
  };

/**
 * Menjalankan beberapa query
 * dalam satu transaksi.
 *
 * Semua query transaksi memakai
 * client PostgreSQL yang sama.
 */
export const withTransaction =
  async <T>(
    callback: (
      client: PoolClient
    ) => Promise<T>
  ): Promise<T> => {
    const client =
      await pool.connect();

    try {
      await client.query('BEGIN');

      const result =
        await callback(client);

      await client.query('COMMIT');

      return result;
    } catch (error) {
      await client.query(
        'ROLLBACK'
      );

      throw error;
    } finally {
      client.release();
    }
  };

/**
 * Menutup seluruh koneksi database.
 *
 * Gunakan ketika aplikasi dihentikan.
 */
export const closeDatabase =
  async (): Promise<void> => {
    await pool.end();

    console.log(
      '[DATABASE] Connection pool closed.'
    );
  };