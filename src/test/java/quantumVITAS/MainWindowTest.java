package quantumVITAS;

import java.util.concurrent.TimeoutException;


import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.testfx.api.FxToolkit;
import org.testfx.framework.junit5.ApplicationTest;
import javafx.scene.input.KeyCode;
import javafx.scene.input.MouseButton;
import javafx.stage.Stage;
import main.Main;

public abstract class MainWindowTest extends ApplicationTest{
	@BeforeAll
	public static void setUpClass() throws Exception {
		Main.setTestMode(true);
		ApplicationTest.launch(Main.class);
	}

	@BeforeEach
	public void setUp() {
	}

	@Override
	public void start(Stage stage) throws Exception {
		stage.show();
	}
	
	@AfterEach
	public void afterTest() throws TimeoutException{
		FxToolkit.hideStage();
		release(new KeyCode[] {});
		release(new MouseButton[] {});
	}
}
