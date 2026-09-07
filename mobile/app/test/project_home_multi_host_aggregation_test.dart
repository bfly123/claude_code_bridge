import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ccb_mobile/ccb_mobile.dart';
import 'package:ccb_mobile/features/project_home/runtime_mode_panel.dart';
import 'support/project_home_test_driver.dart';
import 'support/project_home_test_fakes.dart';

void main() {
  testWidgets('a single stored profile renders the simple project list', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    final host = _pairedHost(hostId: 'a-solo-host', deviceId: 'phone');
    final controller =
        _HostCatalogController()
          ..setProjects('a-solo-host', [_projectPayload('proj_solo')]);

    await _pumpHome(tester, profiles: [host], controller: controller);
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('project-list')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('multi-host-project-list-screen')),
      findsNothing,
    );
  });

  testWidgets('an offline second pairing keeps the single-host project list', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    final online = _pairedHost(hostId: 'a-online-host', deviceId: 'phone');
    final offline = _pairedHost(hostId: 'z-ghost-host', deviceId: 'phone');
    final controller =
        _HostCatalogController()
          ..setProjects('a-online-host', [_projectPayload('proj_live')])
          ..setOffline('z-ghost-host');

    await _pumpHome(
      tester,
      profiles: [online, offline],
      controller: controller,
    );
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    // The offline pairing must not push the phone into the aggregated view.
    expect(find.byKey(const ValueKey('project-list')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('multi-host-project-list-screen')),
      findsNothing,
    );
    expect(
      find.byKey(const ValueKey('project-open-proj_live')),
      findsOneWidget,
    );
  });

  testWidgets('offline pairings are omitted from an aggregated host count', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    final first = _pairedHost(hostId: 'a-online-host', deviceId: 'phone');
    final second = _pairedHost(hostId: 'b-online-host', deviceId: 'phone');
    final offline = _pairedHost(hostId: 'z-offline-host', deviceId: 'phone');
    final controller =
        _HostCatalogController()
          ..setProjects('a-online-host', [_projectPayload('proj_a')])
          ..setProjects('b-online-host', [_projectPayload('proj_b')])
          ..setOffline('z-offline-host');

    await _pumpHome(
      tester,
      profiles: [first, second, offline],
      controller: controller,
      preferredProfile: first,
    );
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    final summary = tester.widget<Text>(
      find.byKey(const ValueKey('multi-host-project-list-summary')),
    );
    expect(summary.data, '2 of 2 hosts online');
    expect(
      find.byKey(const ValueKey('multi-host-group-name-a-online-host/phone')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('multi-host-group-name-b-online-host/phone')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('multi-host-group-name-z-offline-host/phone')),
      findsNothing,
    );
  });

  testWidgets('two stored profiles with one host_id stay single-host', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    // Same host paired from two devices: distinct profiles, one computer.
    final lanRoute = _pairedHost(hostId: 'same-host', deviceId: 'phone');
    final relayRoute = _pairedHost(hostId: 'same-host', deviceId: 'tablet');
    final controller =
        _HostCatalogController()
          ..setProjects('same-host', [_projectPayload('proj_dedup')]);

    await _pumpHome(
      tester,
      profiles: [lanRoute, relayRoute],
      controller: controller,
    );
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('project-list')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('multi-host-project-list-screen')),
      findsNothing,
    );
  });

  testWidgets('a second host coming online switches to the grouped list', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    final first = _pairedHost(hostId: 'a-first-host', deviceId: 'phone');
    final second = _pairedHost(hostId: 'b-second-host', deviceId: 'phone');
    final controller =
        _HostCatalogController()
          ..setProjects('a-first-host', [_projectPayload('proj_first')])
          ..setOffline('b-second-host');

    await _pumpHome(tester, profiles: [first, second], controller: controller);
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('project-list')), findsOneWidget);

    // The second computer powers on: a refresh probes it again.
    controller.setOnline('b-second-host');
    await tester.tap(find.byKey(const ValueKey('project-list-refresh-action')));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey('multi-host-project-list-screen')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('multi-host-group-name-a-first-host/phone')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('multi-host-group-name-b-second-host/phone')),
      findsOneWidget,
    );
  });

  testWidgets('one host dropping offline returns to the single-host list', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    final keeper = _pairedHost(hostId: 'a-keeper-host', deviceId: 'phone');
    final dropper = _pairedHost(hostId: 'b-dropper-host', deviceId: 'phone');
    final controller =
        _HostCatalogController()
          ..setProjects('a-keeper-host', [_projectPayload('proj_keep')])
          ..setProjects('b-dropper-host', [_projectPayload('proj_drop')]);

    await _pumpHome(
      tester,
      profiles: [keeper, dropper],
      controller: controller,
      preferredProfile: keeper,
    );
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey('multi-host-project-list-screen')),
      findsOneWidget,
    );

    controller.setOffline('b-dropper-host');
    await tester.tap(find.byKey(const ValueKey('project-list-refresh-action')));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('project-list')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('project-open-proj_keep')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('multi-host-project-list-screen')),
      findsNothing,
    );
  });

  testWidgets(
    'falling back to one host uses projects from the current refresh',
    (tester) async {
      await setTestSurfaceSize(tester, const Size(390, 844));
      final keeper = _pairedHost(hostId: 'a-fresh-host', deviceId: 'phone');
      final dropper = _pairedHost(hostId: 'b-old-host', deviceId: 'phone');
      final controller =
          _HostCatalogController()
            ..setProjects('a-fresh-host', [_projectPayload('proj_before')])
            ..setProjects('b-old-host', [_projectPayload('proj_drop')]);

      await _pumpHome(
        tester,
        profiles: [keeper, dropper],
        controller: controller,
        preferredProfile: keeper,
      );
      await _activatePairedGatewayListOnly(tester);
      await tester.pumpAndSettle();

      expect(
        find.byKey(const ValueKey('multi-host-project-list-screen')),
        findsOneWidget,
      );

      controller
        ..setProjects('a-fresh-host', [_projectPayload('proj_after')])
        ..setOffline('b-old-host');
      await tester.tap(
        find.byKey(const ValueKey('project-list-refresh-action')),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const ValueKey('project-list')), findsOneWidget);
      expect(
        find.byKey(const ValueKey('project-open-proj_after')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('project-open-proj_before')),
        findsNothing,
      );
    },
  );

  testWidgets(
    'an established active host failure is shown without silent failover',
    (tester) async {
      await setTestSurfaceSize(tester, const Size(390, 844));
      final active = _pairedHost(hostId: 'a-active-host', deviceId: 'phone');
      final standby = _pairedHost(hostId: 'b-standby-host', deviceId: 'phone');
      final controller =
          _HostCatalogController()
            ..setProjects('a-active-host', [_projectPayload('proj_active')])
            ..setProjects('b-standby-host', [_projectPayload('proj_standby')]);
      final activatedHostIds = <String>[];

      await _pumpHome(
        tester,
        profiles: [active, standby],
        controller: controller,
        preferredProfile: active,
        gatewayTerminalTransportFactory: (profile) {
          activatedHostIds.add(profile.profile.hostId);
          return RecordingTerminalTransport();
        },
      );
      await _activatePairedGatewayListOnly(tester);
      await tester.pumpAndSettle();

      controller.setOffline('a-active-host');
      await tester.tap(
        find.byKey(const ValueKey('project-list-refresh-action')),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const ValueKey('project-list-load-error')),
        findsOneWidget,
      );
      expect(activatedHostIds, ['a-active-host']);
    },
  );

  testWidgets('pending probes keep the current view instead of flashing', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    final online = _pairedHost(hostId: 'a-live-host', deviceId: 'phone');
    final slow = _pairedHost(hostId: 'b-slow-host', deviceId: 'phone');
    final controller =
        _HostCatalogController()
          ..setProjects('a-live-host', [_projectPayload('proj_live')])
          ..setGated('b-slow-host', [_projectPayload('proj_slow')]);

    await _pumpHome(tester, profiles: [online, slow], controller: controller);
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    // The slow host has not answered yet, so only one host is settled online
    // and the simple list stays on screen.
    expect(find.byKey(const ValueKey('project-list')), findsOneWidget);

    controller.releaseGated('b-slow-host');
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey('multi-host-project-list-screen')),
      findsOneWidget,
    );
  });

  testWidgets('all hosts offline shows the recoverable catalog error', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    final a = _pairedHost(hostId: 'a-host', deviceId: 'phone');
    final b = _pairedHost(hostId: 'b-host', deviceId: 'phone');
    final controller =
        _HostCatalogController()
          ..setOffline('a-host')
          ..setOffline('b-host');

    await _pumpHome(tester, profiles: [a, b], controller: controller);
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey('project-list-load-error')),
      findsOneWidget,
    );
    // Recovery entries stay reachable from the error surface.
    expect(
      find.byKey(const ValueKey('project-list-retry-button')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('project-list-back-to-setup-button')),
      findsOneWidget,
    );
  });

  testWidgets(
    'a failed preferred host fails over to the other reachable host',
    (tester) async {
      await setTestSurfaceSize(tester, const Size(390, 844));
      // The explicitly preferred profile is offline; the other computer is
      // online.
      final offlinePreferred = _pairedHost(
        hostId: 'a-preferred-host',
        deviceId: 'phone',
      );
      final reachable = _pairedHost(
        hostId: 'z-reachable-host',
        deviceId: 'phone',
      );
      final controller =
          _HostCatalogController()
            ..setOffline('a-preferred-host')
            ..setProjects('z-reachable-host', [
              _projectPayload('proj_failover'),
            ]);

      await _pumpHome(
        tester,
        profiles: [offlinePreferred, reachable],
        controller: controller,
        preferredProfile: offlinePreferred,
      );
      await _activatePairedGatewayListOnly(tester);
      await tester.pumpAndSettle();

      // The reachable computer takes over instead of an error screen.
      expect(find.byKey(const ValueKey('project-list')), findsOneWidget);
      expect(
        find.byKey(const ValueKey('project-open-proj_failover')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('multi-host-project-list-screen')),
        findsNothing,
      );
    },
  );

  testWidgets(
    'a pending preferred host is not failed over until it is offline',
    (tester) async {
      await setTestSurfaceSize(tester, const Size(390, 844));
      final preferred = _pairedHost(
        hostId: 'a-pending-host',
        deviceId: 'phone',
      );
      final reachable = _pairedHost(hostId: 'z-ready-host', deviceId: 'phone');
      final controller =
          _HostCatalogController()
            ..setGated('a-pending-host', [_projectPayload('proj_pending')])
            ..setProjects('z-ready-host', [_projectPayload('proj_ready')]);
      final activatedHostIds = <String>[];

      await _pumpHome(
        tester,
        profiles: [preferred, reachable],
        controller: controller,
        preferredProfile: preferred,
        gatewayTerminalTransportFactory: (profile) {
          activatedHostIds.add(profile.profile.hostId);
          return RecordingTerminalTransport();
        },
      );
      await openConnectionDetails(tester);
      await expandTile(tester, const ValueKey('runtime-mode-panel'));
      final segments = tester.widget<SegmentedButton<AppRuntimeMode>>(
        find.byKey(const ValueKey('runtime-mode-segments')),
      );
      segments.onSelectionChanged?.call({AppRuntimeMode.pairedGateway});
      await tester.pump();

      expect(activatedHostIds, ['a-pending-host']);

      // Resolve the preferred probe as an explicit failure. Only now may the
      // sole reachable computer become active.
      controller.releaseGated('a-pending-host');
      controller.setOffline('a-pending-host');
      await tester.pumpAndSettle();

      expect(activatedHostIds, ['a-pending-host', 'z-ready-host']);
      await dismissConnectionDetails(tester);
      expect(
        find.byKey(const ValueKey('project-open-proj_ready')),
        findsOneWidget,
      );
    },
  );

  testWidgets('single available host is the default terminal target', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    final online = _pairedHost(hostId: 'a-term-host', deviceId: 'phone');
    final offline = _pairedHost(hostId: 'z-term-ghost', deviceId: 'phone');
    final controller =
        _HostCatalogController()
          ..setProjects('a-term-host', [_projectPayload('proj_term')])
          ..setOffline('z-term-ghost');
    final terminalTransport = RecordingTerminalTransport();

    await tester.pumpWidget(
      MaterialApp(
        home: ProjectHomeScreen(
          repository: FakeMobileCcbRepository.demo(),
          profileStore: await _profileStoreWith([online, offline]),
          gatewayRepositoryFactory: controller.repositoryFor,
          gatewayTerminalTransportFactory:
              (profile) =>
                  profile.profile.hostId == 'a-term-host'
                      ? terminalTransport
                      : RecordingTerminalTransport(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    await tester.tap(
      find.byKey(const ValueKey('project-list-terminal-action')),
    );
    await tester.pumpAndSettle();

    // Only one usable computer: the terminal opens directly on it, without a
    // host picker sheet.
    expect(find.byKey(const ValueKey('host-terminal-screen')), findsOneWidget);
    expect(terminalTransport.hostRequests, hasLength(1));
    expect(terminalTransport.hostRequests.single.clientSessionId, 'shell-1');
  });

  testWidgets('offline pairing stays visible and manageable in settings', (
    tester,
  ) async {
    await setTestSurfaceSize(tester, const Size(390, 844));
    final online = _pairedHost(hostId: 'a-kept-host', deviceId: 'phone');
    final offline = _pairedHost(hostId: 'z-stale-host', deviceId: 'phone');
    final controller =
        _HostCatalogController()
          ..setProjects('a-kept-host', [_projectPayload('proj_kept')])
          ..setOffline('z-stale-host');

    final profileStore = await _profileStoreWith([online, offline]);
    await tester.pumpWidget(
      MaterialApp(
        home: ProjectHomeScreen(
          repository: FakeMobileCcbRepository.demo(),
          profileStore: profileStore,
          gatewayRepositoryFactory: controller.repositoryFor,
          gatewayTerminalTransportFactory: (_) => RecordingTerminalTransport(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await _activatePairedGatewayListOnly(tester);
    await tester.pumpAndSettle();

    // The offline pairing is neither deleted nor demoted: the secure store
    // keeps both pairings.
    final storedProfiles = await profileStore.list();
    expect(storedProfiles, hasLength(2));

    // Open the single project, then its connection details: the runtime panel
    // still lists both computers, so the offline one can be selected or
    // removed from there.
    await tester.tap(find.byKey(const ValueKey('project-open-proj_kept')));
    await tester.pumpAndSettle();
    await openConnectionDetails(tester);
    await expandTile(tester, const ValueKey('runtime-mode-panel'));
    final runtimePanel = tester.widget<RuntimeModePanel>(
      find.byType(RuntimeModePanel),
    );
    expect(runtimePanel.profiles, hasLength(2));
    expect(
      runtimePanel.profiles.map((profile) => profile.profile.hostId),
      containsAll(['a-kept-host', 'z-stale-host']),
    );
  });
}

Future<void> _pumpHome(
  WidgetTester tester, {
  required List<GatewayPairedHost> profiles,
  required _HostCatalogController controller,
  GatewayPairedHost? preferredProfile,
  GatewayTerminalTransportFactory? gatewayTerminalTransportFactory,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: ProjectHomeScreen(
        repository: FakeMobileCcbRepository.demo(),
        profileStore: await _profileStoreWith(
          profiles,
          preferredProfile: preferredProfile,
        ),
        gatewayRepositoryFactory: controller.repositoryFor,
        gatewayTerminalTransportFactory:
            gatewayTerminalTransportFactory ??
            (_) => RecordingTerminalTransport(),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _activatePairedGatewayListOnly(WidgetTester tester) async {
  await openConnectionDetails(tester);
  await expandTile(tester, const ValueKey('runtime-mode-panel'));
  final segments = tester.widget<SegmentedButton<AppRuntimeMode>>(
    find.byKey(const ValueKey('runtime-mode-segments')),
  );
  segments.onSelectionChanged?.call({AppRuntimeMode.pairedGateway});
  await tester.pumpAndSettle();
  await dismissConnectionDetails(tester);
}

Future<GatewayHostProfileStore> _profileStoreWith(
  List<GatewayPairedHost> profiles, {
  GatewayPairedHost? preferredProfile,
}) async {
  final store = GatewayHostProfileStore(secureStore: MemorySecureStore());
  for (final profile in profiles) {
    await store.save(profile);
  }
  if (preferredProfile != null) {
    await store.markSuccessful(preferredProfile);
  }
  return store;
}

GatewayPairedHost _pairedHost({
  required String hostId,
  required String deviceId,
}) {
  return GatewayPairedHost(
    profile: GatewayHostProfile(
      hostId: hostId,
      deviceId: deviceId,
      routeProvider: RouteProvider(
        kind: RouteProviderKind.lan,
        gatewayUrl: Uri.parse('http://127.0.0.1:8787'),
      ),
      scopes: const {
        'view',
        'focus',
        'terminal_input',
        'host_terminal',
        'lifecycle',
        'notify',
      },
    ),
    deviceToken: 'token-$hostId-$deviceId',
    projectId: hostId,
  );
}

Map<String, Object?> _projectPayload(String id) {
  final view =
      jsonDecode(jsonEncode(demoProjectViewFixture['view']))
          as Map<String, Object?>;
  view['project'] = <String, Object?>{
    'id': id,
    'root': '/srv/$id',
    'display_name': id,
    'health': 'healthy',
  };
  return <String, Object?>{'view': view};
}

/// Per-host catalog behavior for the aggregation tests: each host maps to a
/// repository whose listProjects either succeeds, fails, or waits for an
/// explicit release, so probe ordering can be scripted per test.
class _HostCatalogController {
  final Map<String, _Gate> _gates = {};
  final Map<String, Object?> _errors = {};
  final Map<String, List<Map<String, Object?>>> _projects = {};
  final Map<String, _ScriptedRepository> _repositories = {};

  void setProjects(String hostId, List<Map<String, Object?>> payloads) {
    _errors.remove(hostId);
    _gates.remove(hostId);
    _projects[hostId] = payloads;
  }

  void setOffline(String hostId) {
    _errors[hostId] = SocketException('host unreachable');
    _gates.remove(hostId);
  }

  void setOnline(String hostId) {
    _errors.remove(hostId);
    _projects.putIfAbsent(hostId, () => []);
  }

  void setGated(String hostId, List<Map<String, Object?>> payloads) {
    _errors.remove(hostId);
    _projects[hostId] = payloads;
    _gates[hostId] = _Gate();
  }

  void releaseGated(String hostId) {
    _gates.remove(hostId)?.release();
  }

  MobileCcbRepository repositoryFor(GatewayPairedHost profile) {
    return _repositories.putIfAbsent(
      profile.profile.hostId,
      () => _ScriptedRepository(this, profile.profile.hostId),
    );
  }
}

class _Gate {
  final _completer = Completer<void>();
  Future<void> get future => _completer.future;
  void release() {
    if (!_completer.isCompleted) {
      _completer.complete();
    }
  }
}

class _ScriptedRepository implements MobileCcbRepository {
  _ScriptedRepository(this._controller, this._hostId);

  final _HostCatalogController _controller;
  final String _hostId;

  FakeMobileCcbRepository? _delegateFor(String projectId) {
    final payloads = _controller._projects[_hostId];
    if (payloads == null) {
      return null;
    }
    for (final payload in payloads) {
      final view = CcbProjectView.fromProjectViewPayload(payload);
      if (view.project.id == projectId) {
        return FakeMobileCcbRepository(projectViewPayload: payload);
      }
    }
    return null;
  }

  @override
  Future<List<CcbProject>> listProjects() async {
    final gate = _controller._gates[_hostId];
    if (gate != null) {
      await gate.future;
    }
    final error = _controller._errors[_hostId];
    if (error != null) {
      throw error;
    }
    final payloads = _controller._projects[_hostId] ?? const [];
    return [
      for (final payload in payloads)
        CcbProjectView.fromProjectViewPayload(payload).project,
    ];
  }

  @override
  Future<CcbProjectView> getProjectView(String projectId) async {
    final gate = _controller._gates[_hostId];
    if (gate != null) {
      await gate.future;
    }
    final error = _controller._errors[_hostId];
    if (error != null) {
      throw error;
    }
    final delegate = _delegateFor(projectId);
    if (delegate == null) {
      throw ArgumentError.value(projectId, 'projectId', 'unknown project');
    }
    return delegate.getProjectView(projectId);
  }

  @override
  Future<CcbAgentConversation> getAgentConversation({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int limit = 50,
    String? cursor,
  }) async {
    final delegate = _delegateFor(projectId);
    if (delegate == null) {
      throw ArgumentError.value(projectId, 'projectId', 'unknown project');
    }
    return delegate.getAgentConversation(
      projectId: projectId,
      agent: agent,
      namespaceEpoch: namespaceEpoch,
      limit: limit,
      cursor: cursor,
    );
  }

  @override
  Future<CcbAgentMessageSubmitResult> submitAgentMessage(
    CcbAgentMessageSubmitRequest request,
  ) {
    final delegate = _delegateFor(request.projectId);
    if (delegate == null) {
      throw ArgumentError.value(
        request.projectId,
        'projectId',
        'unknown project',
      );
    }
    return delegate.submitAgentMessage(request);
  }

  @override
  Future<CcbProjectLifecycleResult> requestLifecycle({
    required String projectId,
    required CcbLifecycleAction action,
  }) {
    final delegate = _delegateFor(projectId);
    if (delegate == null) {
      throw ArgumentError.value(projectId, 'projectId', 'unknown project');
    }
    return delegate.requestLifecycle(projectId: projectId, action: action);
  }

  @override
  Future<GatewayFileUploadResult> uploadFile({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required List<int> bytes,
  }) {
    final delegate = _delegateFor(projectId);
    if (delegate == null) {
      throw ArgumentError.value(projectId, 'projectId', 'unknown project');
    }
    return delegate.uploadFile(
      projectId: projectId,
      agentName: agentName,
      fileName: fileName,
      mimeType: mimeType,
      bytes: bytes,
    );
  }

  @override
  Future<List<int>> downloadFile({
    required String projectId,
    required String agentName,
    required String fileId,
  }) {
    final delegate = _delegateFor(projectId);
    if (delegate == null) {
      throw ArgumentError.value(projectId, 'projectId', 'unknown project');
    }
    return delegate.downloadFile(
      projectId: projectId,
      agentName: agentName,
      fileId: fileId,
    );
  }

  @override
  Future<ReadableTerminalHistory?> getReadableTerminalHistory({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int maxLines = 200,
  }) {
    final delegate = _delegateFor(projectId);
    if (delegate == null) {
      return Future.value(null);
    }
    return delegate.getReadableTerminalHistory(
      projectId: projectId,
      agent: agent,
      namespaceEpoch: namespaceEpoch,
      maxLines: maxLines,
    );
  }

  @override
  Future<CcbProjectView> focusAgent({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
  }) {
    final delegate = _delegateFor(projectId);
    if (delegate == null) {
      throw ArgumentError.value(projectId, 'projectId', 'unknown project');
    }
    return delegate.focusAgent(
      projectId: projectId,
      agent: agent,
      namespaceEpoch: namespaceEpoch,
    );
  }

  @override
  Future<CcbProjectView> focusWindow({
    required String projectId,
    required String window,
    required int namespaceEpoch,
  }) {
    final delegate = _delegateFor(projectId);
    if (delegate == null) {
      throw ArgumentError.value(projectId, 'projectId', 'unknown project');
    }
    return delegate.focusWindow(
      projectId: projectId,
      window: window,
      namespaceEpoch: namespaceEpoch,
    );
  }
}
