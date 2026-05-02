-- 1. Активные карты
SELECT * FROM app_card WHERE status = 'active';

-- 2. Баланс > 1000
SELECT * FROM app_card WHERE balance > 1000;

-- 3. Баланс < 1000
SELECT * FROM app_card WHERE balance < 1000;

-- 4. Телефон +99850
SELECT * FROM app_card WHERE phone LIKE '+99850%';

-- 5. Карты использованные в переводах
SELECT c.card_number, COUNT(t.id) AS transfer_count
FROM app_card c
JOIN app_transfer t
  ON t.sender_card_number = c.card_number
  OR t.receiver_card_number = c.card_number
GROUP BY c.card_number;

-- 6. Карты НЕ использованные
SELECT * FROM app_card
WHERE card_number NOT IN (
    SELECT sender_card_number FROM app_transfer
    UNION
    SELECT receiver_card_number FROM app_transfer
);

-- 7. Телефоны которые делали переводы
SELECT DISTINCT c.phone
FROM app_card c
JOIN app_transfer t ON t.sender_card_number = c.card_number;