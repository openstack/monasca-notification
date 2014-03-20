INSERT INTO alarm (id, tenant_id, name, state, created_at, updated_at) VALUES ('0', '0', 'test Alarm', 'ALARM', NOW(), NOW());
INSERT INTO alarm (id, tenant_id, name, state, created_at, updated_at) VALUES ('1', '0', 'test Okay', 'OK', NOW(), NOW());
INSERT INTO alarm (id, tenant_id, name, state, created_at, updated_at) VALUES ('2', '0', 'test Undetermined', 'UNDETERMINED', NOW(), NOW());

INSERT INTO notification_method (id, tenant_id, name, type, address, created_at, updated_at)
  VALUES ('0', '0', 'test notification', 'EMAIL', 'me@here.com', NOW(), NOW());

INSERT INTO alarm_action (alarm_id, alarm_state, action_id) VALUES ('0', 'OK', '0');
INSERT INTO alarm_action (alarm_id, alarm_state, action_id) VALUES ('0', 'ALARM', '0');
INSERT INTO alarm_action (alarm_id, alarm_state, action_id) VALUES ('0', 'UNDETERMINED', '0');
INSERT INTO alarm_action (alarm_id, alarm_state, action_id) VALUES ('1', 'OK', '0');
INSERT INTO alarm_action (alarm_id, alarm_state, action_id) VALUES ('1', 'ALARM', '0');
INSERT INTO alarm_action (alarm_id, alarm_state, action_id) VALUES ('1', 'UNDETERMINED', '0');
INSERT INTO alarm_action (alarm_id, alarm_state, action_id) VALUES ('2', 'OK', '0');
INSERT INTO alarm_action (alarm_id, alarm_state, action_id) VALUES ('2', 'ALARM', '0');
INSERT INTO alarm_action (alarm_id, alarm_state, action_id) VALUES ('2', 'UNDETERMINED', '0');

