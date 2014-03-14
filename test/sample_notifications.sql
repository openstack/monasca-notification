INSERT INTO alarm (id, tenant_id, name, state, created_at, updated_at) VALUES ('0', '0', 'test Alarm', 'ALARM', NOW(), NOW());
INSERT INTO alarm (id, tenant_id, name, state, created_at, updated_at) VALUES ('1', '0', 'test Okay', 'OK', NOW(), NOW());
INSERT INTO alarm (id, tenant_id, name, state, created_at, updated_at) VALUES ('2', '0', 'test Undetermined', 'UNDETERMINED', NOW(), NOW());


INSERT INTO alarm_action (alarm_id, action_id) VALUES ('0', '0');
INSERT INTO alarm_action (alarm_id, action_id) VALUES ('1', '0');
INSERT INTO alarm_action (alarm_id, action_id) VALUES ('2', '0');

INSERT INTO notification_method (id, tenant_id, name, type, address, created_at, updated_at)
  VALUES ('0', '0', 'test notification', 'EMAIL', 'me@here.com', NOW(), NOW());
