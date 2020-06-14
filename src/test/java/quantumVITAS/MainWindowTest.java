package quantumVITAS;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.testfx.framework.junit5.ApplicationTest;

import javafx.stage.Stage;
import main.Main;

public abstract class MainWindowTest extends ApplicationTest{
	@BeforeAll
	public static void setUpClass() throws Exception {
		ApplicationTest.launch(Main.class);
	}

	@BeforeEach
	public void setUp() {
	}

	@Override
	public void start(Stage stage) throws Exception {
		stage.show();
	}
}
