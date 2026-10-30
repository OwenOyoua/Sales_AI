-- Rôles de profil (sans connexion)
CREATE ROLE ai_directeur NOLOGIN;
CREATE ROLE ai_sav NOLOGIN;
CREATE ROLE ai_vendeur NOLOGIN;

-- Compte de connexion du service IA : lecture seule, requêtes limitées à 10 s
CREATE ROLE ai_login LOGIN PASSWORD 'Test12345!' NOINHERIT;
GRANT ai_directeur, ai_sav, ai_vendeur TO ai_login;
ALTER ROLE ai_login SET statement_timeout = '10s';
ALTER ROLE ai_login SET default_transaction_read_only = on;

GRANT USAGE ON SCHEMA public TO ai_directeur, ai_sav, ai_vendeur;

-- Directeur : toutes les données métier
GRANT SELECT ON customers, sellers, products, orders, order_items,
                order_payments, order_reviews, tickets TO ai_directeur;

-- SAV : pas de paiements
GRANT SELECT ON customers, products, orders, order_items,
                order_reviews, tickets TO ai_sav;

-- Vendeur : uniquement des vues filtrées sur app.seller_id
CREATE VIEW v_order_items AS
  SELECT * FROM order_items
  WHERE seller_id = current_setting('app.seller_id', true);

CREATE VIEW v_orders AS
  SELECT o.order_id, o.status, o.purchased_at, o.approved_at, o.shipped_at,
         o.delivered_at, o.estimated_delivery_at,
         c.city AS customer_city, c.state AS customer_state
  FROM orders o JOIN customers c ON c.customer_id = o.customer_id
  WHERE EXISTS (SELECT 1 FROM order_items i
                WHERE i.order_id = o.order_id
                  AND i.seller_id = current_setting('app.seller_id', true));

CREATE VIEW v_products AS
  SELECT * FROM products
  WHERE product_id IN (SELECT product_id FROM v_order_items);

CREATE VIEW v_reviews AS
  SELECT * FROM order_reviews
  WHERE order_id IN (SELECT order_id FROM v_orders);

GRANT SELECT ON v_order_items, v_orders, v_products, v_reviews TO ai_vendeur;