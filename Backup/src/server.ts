import app from './app.js';

import { env } from './config/env.js';
import {
  closeDatabase,
  testDatabaseConnection,
} from './config/database.js';

const startServer = async (): Promise<void> => {
  try {
    await testDatabaseConnection();

    app.listen(env.PORT, () => {
      console.log(
        `[SERVER] Backend berjalan di http://localhost:${env.PORT}`
      );
    });
  } catch (error) {
    console.error(
      '[SERVER] Database gagal terhubung:',
      error
    );

    await closeDatabase();
    process.exit(1);
  }
};

void startServer();

const shutdown = async (
  signal: string
): Promise<void> => {
  console.log(
    `[SERVER] ${signal} diterima. Menutup server...`
  );

  await closeDatabase();
  process.exit(0);
};

process.on('SIGINT', () => {
  void shutdown('SIGINT');
});

process.on('SIGTERM', () => {
  void shutdown('SIGTERM');
});
