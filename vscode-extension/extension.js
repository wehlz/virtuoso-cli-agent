const vscode = require("vscode");
const { spawn } = require("child_process");

function workspaceRoot() {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length ? folders[0].uri.fsPath : undefined;
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("virtuoso.openTerminal", () => {
      const cwd = workspaceRoot();
      const term = vscode.window.createTerminal({ name: "Virtuoso", cwd });
      term.show();
      term.sendText("python virtuoso.py");
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("virtuoso.startServe", () => {
      const cwd = workspaceRoot();
      const term = vscode.window.createTerminal({ name: "Virtuoso Serve", cwd });
      term.show();
      term.sendText("python virtuoso.py --serve");
      vscode.window.showInformationMessage(
        "Virtuoso IDE server starting on http://127.0.0.1:8765/v1 — see docs/continue_integration.md"
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("virtuoso.sendSelection", () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        return;
      }
      const text = editor.document.getText(editor.selection);
      if (!text) {
        vscode.window.showWarningMessage("Select code or text first.");
        return;
      }
      const cwd = workspaceRoot();
      const term = vscode.window.createTerminal({ name: "Virtuoso", cwd });
      term.show();
      vscode.env.clipboard.writeText(text);
      term.sendText("python virtuoso.py");
      vscode.window.showInformationMessage(
        "Selection copied. In Virtuoso type: /explain then paste (Ctrl+V)."
      );
    })
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
