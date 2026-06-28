-- ============================================
-- EKOS - Sample Enterprise Data (Manufacturing)
-- ============================================

USE ekos_db;

-- ============================================
-- Default Admin User (password: admin123)
-- ============================================
INSERT INTO users (email, username, password_hash, full_name, role) VALUES
('admin@ekos.local', 'admin', '$2b$12$LQv3c1yqBo9SkvXS7QTJPOtCl06g1VQWzj9Y3.wGp3QbiLC2zFfWe', 'System Administrator', 'admin'),
('analyst@ekos.local', 'analyst', '$2b$12$LQv3c1yqBo9SkvXS7QTJPOtCl06g1VQWzj9Y3.wGp3QbiLC2zFfWe', 'Data Analyst', 'analyst'),
('viewer@ekos.local', 'viewer', '$2b$12$LQv3c1yqBo9SkvXS7QTJPOtCl06g1VQWzj9Y3.wGp3QbiLC2zFfWe', 'Report Viewer', 'viewer');

-- ============================================
-- Machine Events (Realistic Manufacturing Data)
-- ============================================
INSERT INTO machine_events (machine_id, machine_name, event_type, description, severity, root_cause, reported_by, department, production_line, downtime_hours, cost_usd, event_date, resolved_at) VALUES

-- Machine X failures (the demo query scenario)
('MCH-X001', 'CNC Milling Machine X', 'failure', 'Spindle bearing overheating detected. Machine auto-shutdown triggered at 2:15 PM. Bearing temperature exceeded 95°C threshold. Production batch #4421 was interrupted mid-cycle.', 'critical', 'Worn spindle bearing - exceeded service life of 8000 hours. Last replacement was 9200 hours ago.', 'John Martinez', 'Manufacturing', 'Line-3', 4.5, 12500.00, '2024-06-03 14:15:00', '2024-06-03 18:45:00'),

('MCH-X001', 'CNC Milling Machine X', 'failure', 'Coolant system failure. Coolant pump pressure dropped below minimum threshold. Machine overheating detected within 12 minutes of pump failure.', 'high', 'Coolant pump impeller cracked due to contaminated coolant. Debris from previous metal shavings accumulated in reservoir.', 'Sarah Chen', 'Manufacturing', 'Line-3', 6.0, 8750.00, '2024-06-12 09:30:00', '2024-06-12 15:30:00'),

('MCH-X001', 'CNC Milling Machine X', 'failure', 'Tool holder clamp malfunction. Emergency stop activated when tool ejected during high-speed operation. Near-miss safety incident reported.', 'critical', 'Hydraulic clamp pressure insufficient. Root cause: hydraulic line micro-leak at junction B7. Leak rate increased over past 2 weeks.', 'Mike Thompson', 'Manufacturing', 'Line-3', 8.0, 15200.00, '2024-06-21 11:00:00', '2024-06-21 19:00:00'),

('MCH-X001', 'CNC Milling Machine X', 'warning', 'Vibration sensors detecting abnormal patterns on Z-axis. Amplitude increased 40% over baseline. Potential alignment issue.', 'medium', NULL, 'Automated Monitoring System', 'Manufacturing', 'Line-3', 0, 0, '2024-06-08 06:00:00', NULL),

('MCH-X001', 'CNC Milling Machine X', 'inspection', 'Scheduled quarterly inspection completed. Found: minor wear on linear guides, coolant filter 80% capacity, electrical connections nominal.', 'low', NULL, 'David Park', 'Maintenance', 'Line-3', 2.0, 500.00, '2024-06-01 08:00:00', '2024-06-01 10:00:00'),

-- Other machines for context
('MCH-Y002', 'Hydraulic Press Y', 'failure', 'Hydraulic cylinder seal failure. Oil leak detected on main press cylinder. Production halted on Line-2.', 'high', 'Seal degradation due to operating temperature exceeding specification during summer months.', 'Lisa Wang', 'Manufacturing', 'Line-2', 3.0, 6500.00, '2024-06-05 13:00:00', '2024-06-05 16:00:00'),

('MCH-Y002', 'Hydraulic Press Y', 'maintenance', 'Preventive maintenance completed. Replaced hydraulic fluid, all seals inspected, pressure test passed.', 'low', NULL, 'Carlos Rodriguez', 'Maintenance', 'Line-2', 4.0, 2200.00, '2024-06-15 07:00:00', '2024-06-15 11:00:00'),

('MCH-Z003', 'Laser Cutting Station Z', 'failure', 'Laser resonator misalignment. Cut quality degraded below tolerance. Scrap rate increased to 15%.', 'high', 'Thermal expansion of mounting frame due to HVAC failure in cutting bay. Ambient temperature reached 38°C.', 'James Wilson', 'Manufacturing', 'Line-1', 5.0, 18000.00, '2024-06-10 10:00:00', '2024-06-10 15:00:00'),

('MCH-Z003', 'Laser Cutting Station Z', 'warning', 'Gas assist pressure fluctuation detected. Nitrogen supply showing irregular flow patterns.', 'medium', NULL, 'Automated Monitoring System', 'Manufacturing', 'Line-1', 0, 0, '2024-06-18 14:30:00', NULL),

('MCH-A004', 'Robotic Welding Arm A', 'failure', 'Servo motor fault on joint 3. Robot entered safe mode. Welding operation on chassis assembly stopped.', 'critical', 'Encoder feedback error caused by electromagnetic interference from nearby equipment.', 'Tom Baker', 'Manufacturing', 'Line-4', 7.0, 9800.00, '2024-06-07 16:00:00', '2024-06-07 23:00:00'),

('MCH-A004', 'Robotic Welding Arm A', 'maintenance', 'Emergency repair: replaced servo motor and encoder on joint 3. Full calibration performed.', 'low', NULL, 'Emily Foster', 'Maintenance', 'Line-4', 3.0, 4500.00, '2024-06-08 08:00:00', '2024-06-08 11:00:00'),

('MCH-B005', 'Conveyor System B', 'warning', 'Belt tension sensor reading outside normal range. Belt showing signs of stretching.', 'medium', NULL, 'Automated Monitoring System', 'Manufacturing', 'Line-1', 0, 0, '2024-06-14 09:00:00', NULL),

('MCH-B005', 'Conveyor System B', 'failure', 'Belt snap during peak load. All units on conveyor dropped. 12 units damaged.', 'critical', 'Belt tension warning from June 14 was not addressed. Belt exceeded elastic limit under load.', 'Amy Johnson', 'Manufacturing', 'Line-1', 10.0, 22000.00, '2024-06-20 11:30:00', '2024-06-20 21:30:00');

-- ============================================
-- Maintenance Logs
-- ============================================
INSERT INTO maintenance_logs (machine_id, machine_name, action_type, description, technician, parts_replaced, parts_cost_usd, labor_cost_usd, total_cost_usd, duration_hours, status, notes, log_date, next_maintenance_date) VALUES

('MCH-X001', 'CNC Milling Machine X', 'emergency', 'Emergency spindle bearing replacement. Removed damaged bearing assembly, cleaned spindle housing, installed new precision bearing set. Performed run-in procedure at graduated speeds.', 'Carlos Rodriguez', 'Spindle bearing set (SKF 7210), bearing grease (Mobil SHC 100)', 8500.00, 2400.00, 10900.00, 4.0, 'completed', 'Recommended reducing spindle RPM by 10% until full break-in (200 hours). Previous bearing lasted 9200 hours vs 8000 hour recommended life.', '2024-06-03 15:00:00', '2024-09-03 08:00:00'),

('MCH-X001', 'CNC Milling Machine X', 'corrective', 'Coolant pump replacement and reservoir cleaning. Drained coolant system, removed debris accumulation, replaced cracked impeller pump, flushed lines, refilled with fresh coolant.', 'Emily Foster', 'Coolant pump assembly (Grundfos CRN-3), coolant filter, 200L cutting fluid', 4200.00, 1800.00, 6000.00, 5.5, 'completed', 'Installed additional inline filter to prevent future debris accumulation. Set up weekly coolant clarity check on maintenance schedule.', '2024-06-12 10:00:00', '2024-07-12 08:00:00'),

('MCH-X001', 'CNC Milling Machine X', 'emergency', 'Hydraulic clamp system overhaul. Located micro-leak at junction B7, replaced hydraulic line section, rebuilt clamp actuator, pressure tested entire hydraulic circuit to 350 bar.', 'Carlos Rodriguez', 'Hydraulic line assembly, junction seals (Parker H-series), hydraulic fluid top-up 5L', 6800.00, 3200.00, 10000.00, 7.5, 'completed', 'SAFETY CONCERN: Tool ejection could have caused injury. Recommend weekly hydraulic pressure checks for next month. Added pressure gauge at junction B7 for continuous monitoring.', '2024-06-21 12:00:00', '2024-07-05 08:00:00'),

('MCH-X001', 'CNC Milling Machine X', 'preventive', 'Quarterly preventive maintenance. Inspected linear guides, replaced coolant filter, checked electrical connections, calibrated tool length sensor, verified axis positioning accuracy.', 'David Park', 'Coolant filter, way lubricant 2L', 350.00, 600.00, 950.00, 2.0, 'completed', 'Linear guides showing minor wear. Estimated remaining life: 6 months. Scheduled replacement for Q4. All axes within positioning tolerance.', '2024-06-01 08:00:00', '2024-09-01 08:00:00'),

('MCH-Y002', 'Hydraulic Press Y', 'corrective', 'Replaced main cylinder seals. Drained hydraulic system, removed cylinder, replaced all seals with high-temperature rated variants.', 'Tom Baker', 'High-temp seal kit (Trelleborg HT-series), hydraulic fluid 50L', 3500.00, 1800.00, 5300.00, 3.0, 'completed', 'Upgraded to high-temperature seals rated for 120°C vs previous 90°C rating. Recommended installing temperature monitor on hydraulic reservoir.', '2024-06-05 13:30:00', '2024-12-05 08:00:00'),

('MCH-Y002', 'Hydraulic Press Y', 'preventive', 'Scheduled preventive maintenance. Replaced hydraulic fluid, inspected all seals, performed pressure test (passed at 500 bar), checked alignment.', 'Carlos Rodriguez', 'Hydraulic fluid 100L, filter elements x3', 1200.00, 1000.00, 2200.00, 4.0, 'completed', 'All systems nominal. New high-temp seals performing well. No leaks detected.', '2024-06-15 07:00:00', '2024-09-15 08:00:00'),

('MCH-Z003', 'Laser Cutting Station Z', 'corrective', 'Laser resonator realignment and calibration. Adjusted mirror mounts, cleaned optics, recalibrated beam path. HVAC system in cutting bay repaired by facilities team.', 'Emily Foster', 'Optics cleaning kit, calibration targets', 1500.00, 2500.00, 4000.00, 4.5, 'completed', 'Cut quality restored to specification. HVAC repair should prevent recurrence. Added ambient temperature alarm at 32°C threshold.', '2024-06-10 10:30:00', '2024-09-10 08:00:00'),

('MCH-A004', 'Robotic Welding Arm A', 'emergency', 'Replaced servo motor and encoder on joint 3. Full 6-axis calibration performed. Added EMI shielding to encoder cables.', 'Emily Foster', 'Servo motor (Fanuc AiF-22/3000), absolute encoder, EMI shielding kit', 7200.00, 2600.00, 9800.00, 6.0, 'completed', 'EMI source identified as new induction heater installed on adjacent Line-5. Shielding should prevent recurrence. Monitoring encoder feedback quality.', '2024-06-08 08:00:00', '2024-09-08 08:00:00'),

('MCH-B005', 'Conveyor System B', 'emergency', 'Belt replacement. Installed new reinforced belt, re-tensioned, calibrated speed sensors. Inspected and repaired damaged rollers.', 'Tom Baker', 'Conveyor belt (Continental Forte, reinforced), rollers x4, tension springs x2', 8500.00, 3000.00, 11500.00, 9.0, 'completed', 'WARNING: Belt tension warning from June 14 was logged but not escalated. Review maintenance alert escalation procedures. 12 production units damaged - quality hold placed.', '2024-06-20 12:00:00', '2024-08-20 08:00:00'),

('MCH-B005', 'Conveyor System B', 'inspection', 'Post-repair inspection. Verified belt tracking, tension, speed accuracy. Load tested at 120% rated capacity.', 'David Park', NULL, 0, 400.00, 400.00, 1.0, 'completed', 'All parameters within specification. Belt running centered. No abnormal vibration detected.', '2024-06-22 08:00:00', '2024-07-22 08:00:00');

-- ============================================
-- Sample Audit Logs
-- ============================================
INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details_json, ip_address) VALUES
(1, 'LOGIN', 'auth', NULL, '{"method": "password"}', '127.0.0.1'),
(1, 'UPLOAD_DOCUMENT', 'document', '1', '{"filename": "maintenance_manual.pdf", "file_size": 2048576}', '127.0.0.1'),
(2, 'QUERY', 'query', '1', '{"query": "Why did Machine X fail?"}', '127.0.0.1');
