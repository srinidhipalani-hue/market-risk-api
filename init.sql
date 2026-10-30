CREATE TABLE IF NOT EXISTS prices (
    ticker  TEXT          NOT NULL,
    date    DATE          NOT NULL,
    close   NUMERIC(12,4) NOT NULL,
    PRIMARY KEY (ticker, date)
);