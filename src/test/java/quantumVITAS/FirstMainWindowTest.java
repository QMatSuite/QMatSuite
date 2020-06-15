package quantumVITAS;

import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.junit.jupiter.api.MethodOrderer;
import org.testfx.api.FxRobotException;
import org.testfx.matcher.control.ComboBoxMatchers;
import org.testfx.service.query.EmptyNodeQueryException;
import org.testfx.util.WaitForAsyncUtils;

import com.consts.Constants.EnumStep;

import javafx.collections.ObservableList;
import javafx.scene.Node;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.ListCell;
import javafx.scene.control.Tab;
import javafx.scene.control.TabPane;
import javafx.scene.control.TreeItem;
import javafx.scene.control.TreeTableView;
import javafx.scene.input.KeyCode;
import javafx.scene.layout.Pane;
import project.ProjectCalcLog;
import org.testfx.api.FxAssert;
import org.testfx.util.WaitForAsyncUtils;

@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
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
	
	@Test
	@Order(4)
	public void testAddCalculation() {
		ComboBox<String> comboCalculation = lookup("#comboCalculation").queryComboBox();
		TabPane tabPaneRight = (TabPane) lookup("#idtabPaneRight").queryParent();
		ObservableList<Tab> tabList;
		
		clickOn("#calcMain");
		clickOn("#calcScf");
		FxAssert.verifyThat(comboCalculation, ComboBoxMatchers.containsExactlyItems("SCF_1"));
		//Assertions.assertTrue(comboCalculation.getSelectionModel().getSelectedItem().toLowerCase().contains("scf"));
		tabList = tabPaneRight.getTabs();
		Assertions.assertTrue(tabList.size()==2);//geo and scf tab
		
		clickOn("#calcMain");
		clickOn("#calcOpt");
		FxAssert.verifyThat(comboCalculation, ComboBoxMatchers.containsExactlyItems("SCF_1","OPT_1"));
		//Assertions.assertTrue(comboCalculation.getSelectionModel().getSelectedItem().toLowerCase().contains("opt"));
		tabList = tabPaneRight.getTabs();
		Assertions.assertTrue(tabList.size()==3);//geo, scf and opt

		clickOn("#calcMain");
		clickOn("#calcMd");
		FxAssert.verifyThat(comboCalculation, ComboBoxMatchers.containsExactlyItems("SCF_1","OPT_1","BOMD_1"));
		//Assertions.assertTrue(comboCalculation.getSelectionModel().getSelectedItem().toLowerCase().contains("md"));
		tabList = tabPaneRight.getTabs();
		Assertions.assertTrue(tabList.size()==3);//geo, scf and md
	}
	
	@Test
	@Order(5)
	public void testGoToCalculation() {
		ComboBox<String> comboCalculation = lookup("#comboCalculation").queryComboBox();
		TabPane tabPaneRight = (TabPane) lookup("#idtabPaneRight").queryParent();
		
		clickOn("#comboCalculation");
		selectComboBox(comboCalculation, 0);
		checkRightPaneTabs(comboCalculation, 0, tabPaneRight);
		//sleep(1000);
		
		clickOn("#comboCalculation");
		selectComboBox(comboCalculation, 1);
		checkRightPaneTabs(comboCalculation, 1, tabPaneRight);
		//sleep(1000);
		
		clickOn("#comboCalculation");
		selectComboBox(comboCalculation, 2);
		checkRightPaneTabs(comboCalculation, 2, tabPaneRight);
		//sleep(1000);
		
		
	}
	private void checkRightPaneTabs(ComboBox<String> cb, int iExpected, TabPane tabPaneRight) {
		int iSelected = cb.getSelectionModel().getSelectedIndex();
		Assertions.assertEquals(iSelected, iExpected,Integer.toString(iSelected)+Integer.toString(iExpected));
		
		String selectItem = cb.getSelectionModel().getSelectedItem().toLowerCase();
		ObservableList<Tab> tabList = tabPaneRight.getTabs();
		
		if(selectItem.contains("scf")&&!selectItem.contains("nscf")) {Assertions.assertTrue(tabList.size()==2,"scf"+Integer.toString(tabList.size()));}
		if(selectItem.contains("opt")) {Assertions.assertTrue(tabList.size()==3,"opt"+Integer.toString(tabList.size()));}
		if(selectItem.contains("md")) {Assertions.assertTrue(tabList.size()==3,"md"+Integer.toString(tabList.size()));}
	}
	private <T> void selectComboBox(ComboBox<T> cb, int i) {
		if(i<0 || i>cb.getItems().size()) {Assertions.assertTrue(false,"Index out of bound");return;}
		
		Set<Node> allListCells = lookup(cb.getItems().get(i).toString()).queryAll();
				
		String msg="";
		Node nd_tmp=null;
		for(Node nd : allListCells) {
			if(nd.getStyleClass().contains("list-cell")) {
				nd_tmp = nd;
				msg+=nd.toString()+",yes,\n";
				
			}
			else {
				msg+=nd.toString()+",no,\n";
			}
		}
		Assertions.assertTrue(nd_tmp!=null,msg);
		clickOn(nd_tmp);
	}
	
}
