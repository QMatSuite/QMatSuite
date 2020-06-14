package quantumVITAS;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.testfx.api.FxRobotException;
import org.testfx.service.query.EmptyNodeQueryException;
import javafx.collections.ObservableList;
import javafx.scene.control.Label;
import javafx.scene.control.TreeItem;
import javafx.scene.control.TreeTableView;
import project.ProjectCalcLog;

public class FirstMainWindowTest extends MainWindowTest{
	
	@Test
	@Order(1)
	public void testButtonException() {
		Assertions.assertThrows(FxRobotException.class, () -> {
		    clickOn("#anyButtonNonExisting");
		  });
		Assertions.assertThrows(EmptyNodeQueryException.class, () -> {
			lookup("#anyLabelNonExisting").queryLabeled();
		  });
	}
	
	@Test
	@Order(2)
	public void testSetupWorkSpace() {
		clickOn("#buttonOpenWorkSpace");
		Label textWorkSpace = (Label) lookup("#textWorkSpace").queryLabeled();
		Assertions.assertTrue(textWorkSpace.getText().contains("testfx"),"textWorkSpace string should contain 'testfx' in the folder name");
	}
	
	@Test
	@Order(3)
	public void testCreateProject() {
		clickOn("#createProject");
		//Button createProject = lookup("#createProject").queryButton();
		TreeTableView<ProjectCalcLog> projectTree = lookup("#projectTree").queryAs(TreeTableView.class);
		ObservableList<TreeItem<ProjectCalcLog>> obs = projectTree.getRoot().getChildren();
		for(int i=0;i<obs.size();i++) {
			Assertions.assertTrue(obs.get(i).getValue().getProject().contains("testProject"),
					"projectTree selected item should contain 'testProject'");
		}
		
	}
	
	
	
}
